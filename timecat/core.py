"""TimeCat local durable memory. Standard library only; no autonomous I/O beyond local DB."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ALLOWED = {"event", "fact", "lesson", "goal", "preference", "experiment", "identity"}
STATUSES = {"proposed", "approved", "rejected", "superseded"}
def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
def connect(path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS experiences(
      id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL,
      content TEXT NOT NULL, source TEXT NOT NULL, dedupe_key TEXT NOT NULL UNIQUE);
    CREATE TABLE IF NOT EXISTS memories(
      id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL,
      content TEXT NOT NULL, source TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('proposed','approved','rejected','superseded')),
      supersedes INTEGER REFERENCES memories(id));
    CREATE TABLE IF NOT EXISTS reflections(
      id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, period TEXT NOT NULL,
      evidence_ids TEXT NOT NULL, summary TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('proposed','approved','rejected')),
      dedupe_key TEXT NOT NULL UNIQUE);
    CREATE INDEX IF NOT EXISTS idx_memory_status ON memories(status,kind);
    """)
    db.commit()
    return db
def _validate(kind, content, source):
    if kind not in ALLOWED: raise ValueError("unsupported kind")
    if not isinstance(content,str) or not content.strip() or len(content)>4000:
        raise ValueError("empty or excessive content")
    if not isinstance(source,str) or not source.strip() or len(source)>500:
        raise ValueError("source/provenance required")
def record(db, kind, content, source, dedupe_key=None):
    _validate(kind,content,source)
    key=dedupe_key or hashlib.sha256((kind+"\\0"+source+"\\0"+content).encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO experiences(created_at,kind,content,source,dedupe_key) VALUES(?,?,?,?,?)",
               (utcnow(),kind,content,source,key))
    db.commit()
    return dict(db.execute("SELECT * FROM experiences WHERE dedupe_key=?",(key,)).fetchone())
def propose(db, kind, content, source, supersedes=None):
    _validate(kind,content,source)
    if supersedes is not None:
        old=db.execute("SELECT status FROM memories WHERE id=?",(supersedes,)).fetchone()
        if old is None or old["status"]!="approved":raise ValueError("correction must target approved memory")
    cur=db.execute("INSERT INTO memories(created_at,kind,content,source,status,supersedes) VALUES(?,?,?,?,'proposed',?)",
                   (utcnow(),kind,content,source,supersedes))
    db.commit()
    return cur.lastrowid
def review(db, memory_id, approved):
    with db:
        row=db.execute("SELECT status,supersedes FROM memories WHERE id=?",(memory_id,)).fetchone()
        if row is None or row["status"]!="proposed":raise ValueError("memory is not awaiting review")
        if approved and row["supersedes"] is not None:
            cur=db.execute("UPDATE memories SET status='superseded' WHERE id=? AND status='approved'",
                           (row["supersedes"],))
            if cur.rowcount!=1:raise ValueError("superseded memory no longer approved")
        db.execute("UPDATE memories SET status=? WHERE id=?",
                   ("approved" if approved else "rejected",memory_id))
def recall(db, query="", limit=10):
    limit=max(1,min(int(limit),100))
    rows=[dict(r) for r in db.execute("SELECT * FROM memories WHERE status='approved' ORDER BY id DESC LIMIT 1000")]
    if not query.strip():return rows[:limit]
    tokens=query.casefold().split()
    def score(row):
        s=row["content"].casefold()
        return sum(int(t in s) for t in tokens)+(5 if query.casefold() in s else 0)
    return [r for r in sorted(rows,key=lambda r:(score(r),r["id"]),reverse=True) if score(r)>0][:limit]
def propose_reflection(db, period, summary):
    if not period or not summary.strip():raise ValueError("period and summary required")
    evidence=[r["id"] for r in db.execute("SELECT id FROM experiences ORDER BY id DESC LIMIT 100")]
    if not evidence:return None
    key=hashlib.sha256(("reflection:"+period).encode()).hexdigest()
    cur=db.execute("INSERT OR IGNORE INTO reflections(created_at,period,evidence_ids,summary,status,dedupe_key) VALUES(?,?,?,?,'proposed',?)",
                   (utcnow(),period,json.dumps(evidence),summary[:4000],key))
    db.commit()
    return cur.lastrowid if cur.rowcount else None
def snapshot(db):
    return {"experiences":db.execute("SELECT COUNT(*) FROM experiences").fetchone()[0],
            "approved_memories":db.execute("SELECT COUNT(*) FROM memories WHERE status='approved'").fetchone()[0],
            "pending_memories":db.execute("SELECT COUNT(*) FROM memories WHERE status='proposed'").fetchone()[0],
            "pending_reflections":db.execute("SELECT COUNT(*) FROM reflections WHERE status='proposed'").fetchone()[0]}
