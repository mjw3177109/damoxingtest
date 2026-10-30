"""Tests for cloud-authoritative mentor context; fake cloud is not a live Supabase test."""
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from timecat import cloud_cli
from timecat.cloud_memory import MemoryStore, SyncError, synchronize
from timecat.mentor_context import load_approved_context


class FakeCloud:
    def __init__(self):
        self.rows = {}
        self.get_calls = 0
        self.list_calls = 0
        self.create_calls = 0
        self.update_calls = 0

    def get(self, uid):
        self.get_calls += 1
        row = self.rows.get(uid)
        return row.copy() if row else None

    def list_all(self):
        self.list_calls += 1
        return [row.copy() for row in self.rows.values()]

    def create(self, entry):
        self.create_calls += 1
        row = {
            key: entry[key]
            for key in (
                "id", "kind", "content", "source", "status",
                "created_at", "updated_at",
            )
        }
        row["revision"] = 1
        if row["id"] in self.rows:
            raise SyncError("duplicate test record")
        self.rows[row["id"]] = row.copy()
        return row.copy()

    def update(self, entry):
        self.update_calls += 1
        row = self.rows.get(entry["id"])
        if row is None or row["revision"] != entry["remote_revision"]:
            raise SyncError("stale test revision")
        row.update(
            status=entry["status"],
            updated_at=entry["updated_at"],
            revision=row["revision"] + 1,
        )
        return row.copy()


class BrokenCloud(FakeCloud):
    def get(self, uid):
        raise SyncError("remote unavailable; local outbox retained")

    def list_all(self):
        raise SyncError("remote unavailable; local outbox retained")


class MentorContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cloud = FakeCloud()
        self.first = MemoryStore(self.root / "first.sqlite")

    def tearDown(self):
        self.first.close()
        self.tmp.cleanup()

    def test_context_read_never_pushes_local_outbox(self):
        proposed_id = self.first.propose(
            "lesson", "pending proposed record", "local-proposed-fixture"
        )
        approved_id = self.first.propose(
            "preference", "locally approved but not uploaded", "local-approved-fixture"
        )
        self.first.review(approved_id, True)
        rejected_id = self.first.propose(
            "fact", "locally rejected but not uploaded", "local-rejected-fixture"
        )
        self.first.review(rejected_id, False)

        result = load_approved_context(self.cloud)

        self.assertTrue(result["cloud_confirmed"])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["read"]["remote_write_performed"], False)
        self.assertEqual(self.cloud.rows, {})
        self.assertEqual(self.cloud.get_calls, 0)
        self.assertEqual(self.cloud.create_calls, 0)
        self.assertEqual(self.cloud.update_calls, 0)
        self.assertEqual(self.cloud.list_calls, 1)
        self.assertEqual(self.first.counts()["unsynced"], 3)
        self.assertEqual(
            {proposed_id, approved_id, rejected_id},
            {row["id"] for row in self.first.pending()},
        )

    def test_context_cli_does_not_initialize_local_database(self):
        db_path = self.root / "context-read-only.sqlite"
        with patch.object(
            cloud_cli.SupabaseMemoryClient, "from_environment", return_value=self.cloud
        ), patch.object(
            cloud_cli, "load_approved_context", return_value={"cloud_confirmed": True, "records": []}
        ):
            with redirect_stdout(StringIO()):
                exit_code = cloud_cli.main(
                    ["--db", str(db_path), "context", "bobo师傅"]
                )

        self.assertEqual(exit_code, 0)
        self.assertFalse(db_path.exists())

    def test_new_session_reads_only_approved_cloud_memory(self):
        memory_id = self.first.propose(
            "preference",
            "synthetic fixture: prefer approved guidance",
            "synthetic-test-fixture",
        )
        self.first.review(memory_id, True)
        synchronize(self.first, self.cloud)
        self.cloud.rows[memory_id]["owner_id"] = "must-not-enter-prompt"

        second = MemoryStore(self.root / "second.sqlite")
        try:
            result = load_approved_context(self.cloud, "approved guidance")
            self.assertTrue(result["cloud_confirmed"])
            self.assertEqual(result["authority"], "supabase_user_jwt_rls")
            self.assertEqual(len(result["records"]), 1)
            record = result["records"][0]
            self.assertEqual(record["id"], memory_id)
            self.assertEqual(record["revision"], 1)
            self.assertEqual(record["source"], "synthetic-test-fixture")
            self.assertNotIn("status", record)
            self.assertNotIn("owner_id", record)
        finally:
            second.close()

    def test_proposed_and_rejected_records_never_enter_context(self):
        proposed_id = self.first.propose(
            "lesson", "draft-only secret phrase", "test-source"
        )
        rejected_id = self.first.propose(
            "fact", "rejected secret phrase", "test-source"
        )
        self.first.review(rejected_id, False)
        synchronize(self.first, self.cloud)

        result = load_approved_context(self.cloud, "secret phrase")
        self.assertEqual(result["records"], [])
        self.assertIn(proposed_id, self.cloud.rows)
        self.assertIn(rejected_id, self.cloud.rows)

    def test_context_uses_fresh_cloud_snapshot_not_tampered_local_cache(self):
        memory_id = self.first.propose(
            "lesson", "original approved guidance", "verified-source"
        )
        self.first.review(memory_id, True)
        synchronize(self.first, self.cloud)

        # Simulate a stale or locally altered SQLite cache without a dirty flag.
        with self.first.db:
            self.first.db.execute(
                "UPDATE cloud_memories SET content=? WHERE id=?",
                ("tampered local guidance", memory_id),
            )

        result = load_approved_context(self.cloud, "original approved")
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["content"], "original approved guidance")
        self.assertNotIn("tampered", result["records"][0]["content"])

    def test_cloud_failure_fails_closed_without_local_fallback(self):
        memory_id = self.first.propose(
            "preference", "approved but not cloud-confirmed", "test-source"
        )
        self.first.review(memory_id, True)
        with self.assertRaises(SyncError):
            load_approved_context(BrokenCloud(), "approved")
        # The local record remains pending for later sync, but was not returned.
        self.assertEqual(self.first.counts()["unsynced"], 1)

    def test_query_filters_approved_records_deterministically(self):
        match_id = self.first.propose(
            "goal", "准确召回师傅批准的指导", "source-a"
        )
        other_id = self.first.propose(
            "fact", "与天气无关的记录", "source-b"
        )
        self.first.review(match_id, True)
        self.first.review(other_id, True)
        synchronize(self.first, self.cloud)

        result = load_approved_context(self.cloud, "准确召回")
        self.assertEqual([row["id"] for row in result["records"]], [match_id])

    def test_context_limit_is_bounded(self):
        for index in range(4):
            uid = self.first.propose(
                "fact", "approved memory " + str(index), "source-" + str(index)
            )
            self.first.review(uid, True)
        synchronize(self.first, self.cloud)
        result = load_approved_context(self.cloud, "", 2)
        self.assertEqual(len(result["records"]), 2)

    def test_invalid_query_type_is_rejected(self):
        with self.assertRaises(ValueError):
            load_approved_context(self.cloud, None)


if __name__ == "__main__":
    unittest.main()
