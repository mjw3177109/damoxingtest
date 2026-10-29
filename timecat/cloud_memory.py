"""TimeCat V2 private memory: SQLite outbox + Supabase PostgREST user-JWT sync.

The cloud becomes authoritative only after both push and pull succeed.
Never supply a service-role key here. Do not use this module for public GitHub logs.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

KINDS = frozenset({"fact", "lesson", "goal", "preference", "event", "experiment"})
STATUSES = frozenset({"proposed", "approved", "rejected"})
FIELDS = "id,kind,content,source,status,created_at,updated_at,revision"
MAX_LEN = 4000


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SyncError(RuntimeError):
    pass


class SyncConflict(SyncError):
    pass


def _validate(kind, content, source):
    if kind not in KINDS:
        raise ValueError("invalid memory kind")
    if not isinstance(content, str) or not content.strip() or len(content) > MAX_LEN:
        raise ValueError("empty or excessive memory content")
    if not isinstance(source, str) or not source.strip() or len(source) > 500:
        raise ValueError("verifiable source required")


class MemoryStore:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS cloud_memories(
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, content TEXT NOT NULL,
                source TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                remote_revision INTEGER NOT NULL DEFAULT 0,
                dirty INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS ix_cloud_memories_status
                ON cloud_memories(status,updated_at);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def get(self, uid):
        row = self.db.execute("SELECT * FROM cloud_memories WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None

    def propose(self, kind, content, source, uid=None):
        _validate(kind, content, source)
        uid = str(uuid.UUID(uid)) if uid else str(uuid.uuid4())
        stamp = now()
        with self.db:
            self.db.execute(
                """INSERT INTO cloud_memories
                  (id,kind,content,source,status,created_at,updated_at,revision,remote_revision,dirty)
                   VALUES(?,?,?,?,'proposed',?,?,1,0,1)""",
                (uid, kind, content.strip(), source.strip(), stamp, stamp))
        return uid

    def review(self, uid, approve):
        with self.db:
            row = self.get(uid)
            if not row or row["status"] != "proposed":
                raise ValueError("only proposed memories can be reviewed")
            self.db.execute("""UPDATE cloud_memories SET status=?,updated_at=?,
                          revision=revision+1,dirty=1 WHERE id=?""",
                          ("approved" if approve else "rejected", now(), uid))

    def recall(self, query="", limit=20):
        limit = max(1, min(100, int(limit)))
        rows = [dict(r) for r in self.db.execute(
            "SELECT * FROM cloud_memories WHERE status='approved' ORDER BY updated_at DESC,id DESC LIMIT 2000")]
        tokens = query.casefold().split()
        if tokens:
            rows = [r for r in rows if all(t in r["content"].casefold() for t in tokens)]
        return [{k:r[k] for k in ("id","kind","content","source","updated_at")}
                for r in rows[:limit]]

    def pending(self):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM cloud_memories WHERE dirty=1 ORDER BY created_at,id")]

    def _ack(self, remote):
        uid = remote["id"]
        # Atomic ack: local changes are not silently lost if another process wrote first.
        current = self.get(uid)
        if not current or not current["dirty"]:
            raise SyncConflict("local memory changed before ack")
        with self.db:
            cur = self.db.execute(
                """UPDATE cloud_memories SET revision=?,remote_revision=?,dirty=0
                   WHERE id=? AND dirty=1 AND revision=? AND remote_revision=?""",
                (remote["revision"],remote["revision"],uid,current["revision"],current["remote_revision"]))
            if cur.rowcount != 1:
                raise SyncConflict("local concurrent update detected")

    def import_remote(self, remote):
        for entry in remote:
            _validate(entry["kind"],entry["content"],entry["source"])
            if entry["status"] not in STATUSES:
                raise SyncError("unexpected remote memory status")
            uuid.UUID(entry["id"])
            rev = int(entry["revision"])
            if rev < 1:
                raise SyncError("invalid remote revision")
            local = self.get(entry["id"])
            if local and local["dirty"]:
                if rev > local["remote_revision"]:
                    raise SyncConflict("remote edit conflicts with unsynced local data")
                continue
            if local and rev < local["remote_revision"]:
                raise SyncError("remote revision went backwards")
            if not local or rev > local["remote_revision"]:
                with self.db:
                    self.db.execute(
                        """INSERT INTO cloud_memories(id,kind,content,source,status,created_at,updated_at,
                              revision,remote_revision,dirty) VALUES(?,?,?,?,?,?,?,?,?,0)
                           ON CONFLICT(id) DO UPDATE SET
                              kind=excluded.kind,content=excluded.content,source=excluded.source,
                              status=excluded.status,created_at=excluded.created_at,updated_at=excluded.updated_at,
                              revision=excluded.revision,remote_revision=excluded.remote_revision,dirty=0""",
                        (entry["id"],entry["kind"],entry["content"],entry["source"],
                         entry["status"],entry["created_at"],entry["updated_at"],rev,rev))
        return len(remote)

    def counts(self):
        row = self.db.execute(
            """SELECT COUNT(*) AS total, COALESCE(SUM(status='approved'),0) AS approved,
               COALESCE(SUM(status='proposed'),0) AS proposed,
               COALESCE(SUM(dirty),0) AS unsynced FROM cloud_memories""").fetchone()
        return dict(row)


class SupabaseMemoryClient:
    def __init__(self, url, publishable_key, user_access_token, requester=None):
        url = url.rstrip("/")
        if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url):
            raise ValueError("Supabase project URL must be https://<project>.supabase.co")
        if not publishable_key or not user_access_token:
            raise ValueError("missing publishable key or user access JWT")
        if publishable_key == user_access_token:
            raise ValueError("an authenticated user JWT is required separately")
        self.url = url + "/rest/v1/timecat_memory_v2"
        self.key = publishable_key
        self.jwt = user_access_token
        self._requester = requester

    @classmethod
    def from_environment(cls):
        return cls(os.environ.get("TIMECAT_SUPABASE_URL",""),
                   os.environ.get("TIMECAT_SUPABASE_PUBLISHABLE_KEY",""),
                   os.environ.get("TIMECAT_SUPABASE_ACCESS_TOKEN",""))

    def _call(self, method, query="", data=None):
        headers = {"apikey":self.key,"Authorization":"Bearer "+self.jwt,
                   "Accept":"application/json","Content-Type":"application/json",
                   "Prefer":"return=representation"}
        url = self.url + ("?"+query if query else "")
        body = json.dumps(data,ensure_ascii=False).encode("utf-8") if data is not None else None
        if self._requester:
            return self._requester(method,url,headers,body)
        req = Request(url,headers=headers,data=body,method=method)
        try:
            with urlopen(req,timeout=20) as response:
                result = response.read(4_000_000)
                return json.loads(result) if result else []
        except HTTPError as exc:
            # Do not include sensitive response bodies or Authorization headers.
            raise SyncError("remote HTTP %d; no private data logged" % exc.code) from None
        except URLError:
            raise SyncError("remote unavailable; local outbox retained") from None

    def get(self, uid):
        data = self._call("GET","select="+FIELDS+"&id=eq."+quote(uid)+"&limit=1")
        return data[0] if data else None

    def list_all(self):
        offset=0
        results=[]
        while True:
            page=self._call("GET","select="+FIELDS+"&order=created_at.asc,id.asc&limit=200&offset="+str(offset))
            if not isinstance(page,list):
                raise SyncError("invalid cloud response")
            results.extend(page)
            if len(page)<200:
                return results
            offset+=200
            if offset>=20000:
                raise SyncError("sync page cap exceeded; no partial import")

    def create(self, entry):
        obj={k:entry[k] for k in ("id","kind","content","source","status","created_at","updated_at")}
        obj["revision"]=1
        data=self._call("POST",data=obj)
        if len(data)!=1 or data[0]["id"]!=entry["id"]:
            raise SyncError("remote insert not acknowledged")
        return data[0]

    def update(self, entry):
        rev = entry["remote_revision"]
        obj={"status":entry["status"],"updated_at":entry["updated_at"],"revision":rev+1}
        data=self._call("PATCH","id=eq."+quote(entry["id"])+"&revision=eq."+str(rev),obj)
        if len(data)!=1:
            raise SyncConflict("remote revision conflict; did not overwrite")
        return data[0]


def synchronize(store, cloud):
    """Push unsynced approved/rejected/proposed changes, then re-read cloud.

    Proposed memories are synced but NEVER treated as approved by recall.
    A failed push or conflict leaves pending local changes for review.
    """
    uploaded=0
    for entry in store.pending():
        remote=cloud.get(entry["id"])
        if entry["remote_revision"] == 0:
            if remote:
                # An ID collision or partial past upload: only auto-ack exactly same data.
                if any(remote[k]!=entry[k] for k in ("kind","content","source","status")):
                    raise SyncConflict("existing remote ID has different data")
            else:
                remote=cloud.create(entry)
        else:
            if not remote or int(remote["revision"])!=entry["remote_revision"]:
                raise SyncConflict("remote changed; preserve local unsynced memory")
            remote=cloud.update(entry)
        store._ack(remote)
        uploaded+=1
    downloaded=store.import_remote(cloud.list_all())
    return {"uploaded":uploaded,"cloud_records_seen":downloaded,
            "local":store.counts(), "cloud_confirmed":True}
