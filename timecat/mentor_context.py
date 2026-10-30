"""Build fail-closed conversation context from cloud-confirmed approved memories.

This module deliberately re-reads Supabase after synchronization and builds the
context from that response, not from a possibly stale or locally modified cache.
It never elevates proposed memories and never falls back to local recall.
"""
from __future__ import annotations

import uuid

from .cloud_memory import SyncError, synchronize

_ALLOWED_KINDS = {"fact", "lesson", "goal", "preference", "event", "experiment"}
_ALLOWED_STATUSES = {"proposed", "approved", "rejected"}


def _normalize_cloud_record(raw):
    if not isinstance(raw, dict):
        raise SyncError("invalid cloud memory record")
    try:
        uid = str(uuid.UUID(str(raw["id"])))
        kind = raw["kind"]
        content = raw["content"]
        source = raw["source"]
        status = raw["status"]
        revision = int(raw["revision"])
        created_at = raw["created_at"]
        updated_at = raw["updated_at"]
    except (KeyError, TypeError, ValueError):
        raise SyncError("cloud memory record is missing required fields") from None

    if (
        not isinstance(kind, str)
        or kind not in _ALLOWED_KINDS
        or not isinstance(status, str)
        or status not in _ALLOWED_STATUSES
    ):
        raise SyncError("cloud memory record has an unsupported kind or status")
    if not isinstance(content, str) or not content.strip() or len(content) > 4000:
        raise SyncError("cloud memory record has invalid content")
    if not isinstance(source, str) or not source.strip() or len(source) > 500:
        raise SyncError("cloud memory record has invalid provenance")
    if revision < 1:
        raise SyncError("cloud memory record has an invalid revision")
    if not isinstance(created_at, str) or not created_at:
        raise SyncError("cloud memory record has no creation timestamp")
    if not isinstance(updated_at, str) or not updated_at:
        raise SyncError("cloud memory record has no update timestamp")

    # Do not expose owner_id or any other database fields to the prompt.
    return {
        "id": uid,
        "kind": kind,
        "content": content,
        "source": source,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "revision": revision,
    }


def _query_score(record, query):
    query = query.casefold().strip()
    if not query:
        return 0
    haystack = " ".join(
        (record["kind"], record["content"], record["source"])
    ).casefold()
    if query in haystack:
        return 100 + len(query)
    terms = [term for term in query.split() if term]
    if not terms:
        return 0
    hits = sum(1 for term in terms if term in haystack)
    return hits if hits == len(terms) else 0


def load_approved_context(store, cloud, query="", limit=10):
    """Sync, re-read the authenticated cloud, and return approved records only.

    Any auth, network, conflict, or validation failure raises; callers must not
    silently substitute local-only recall. The cloud client must use the user's
    JWT so Supabase RLS scopes the result to that user's records.
    """
    if not isinstance(query, str):
        raise ValueError("query must be text")
    limit = max(1, min(100, int(limit)))

    sync_result = synchronize(store, cloud)
    if not isinstance(sync_result, dict) or sync_result.get("cloud_confirmed") is not True:
        raise SyncError("cloud synchronization was not confirmed")

    # Read a fresh authoritative snapshot after push/pull. Do not build prompts
    # from the SQLite cache: it may contain stale or locally modified rows.
    remote_rows = cloud.list_all()
    if not isinstance(remote_rows, list):
        raise SyncError("invalid cloud memory list response")

    normalized = [_normalize_cloud_record(row) for row in remote_rows]
    ranked = []
    for record in normalized:
        if record["status"] != "approved":
            continue
        score = _query_score(record, query)
        if query.strip() and score == 0:
            continue
        ranked.append((score, record))

    ranked.sort(
        key=lambda pair: (
            pair[0],
            pair[1]["updated_at"],
            pair[1]["id"],
        ),
        reverse=True,
    )
    records = [
        {
            key: record[key]
            for key in ("id", "kind", "content", "source", "updated_at", "revision")
        }
        for _, record in ranked[:limit]
    ]

    return {
        "schema_version": 1,
        "authority": "supabase_user_jwt_rls",
        "cloud_confirmed": True,
        "query": query,
        "sync": {
            "uploaded": int(sync_result.get("uploaded", 0)),
            "cloud_records_seen": len(normalized),
        },
        "records": records,
        "usage_policy": (
            "Use only these approved records as mentor guidance. Preserve their "
            "meaning, do not infer additional preferences, and retain each source "
            "and revision when auditing how guidance was applied."
        ),
    }
