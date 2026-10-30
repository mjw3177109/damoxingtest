"""Offline contract tests for the exact-snapshot no-GPU hold."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import inference_only_submission_hold as hold


class InferenceOnlySubmissionHoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = {
            "scripts/train_gpt2_lora.py": b"audited inference-only script",
            "kaggle/gpt2_training.ipynb": b"audited notebook",
            "requirements-kaggle.txt": b"audited dependencies",
            "data/safety_humanity_train_v2.jsonl": b"audited training data",
            "data/safety_humanity_eval_v1.jsonl": b"audited evaluation data",
        }
        for path, data in self.paths.items():
            dest = self.root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        blobs = {path: hold.git_blob_sha(self.root / path)
                 for path in hold.EXPECTED_GIT_BLOBS}
        hashes = {path: hashlib.sha256((self.root / path).read_bytes()).hexdigest()
                  for path in hold.EXPECTED_DATA_SHA256}
        p1 = patch.dict(hold.EXPECTED_GIT_BLOBS, blobs, clear=True)
        p2 = patch.dict(hold.EXPECTED_DATA_SHA256, hashes, clear=True)
        p1.start()
        p2.start()
        self.addCleanup(p2.stop)
        self.addCleanup(p1.stop)

    def test_exact_snapshot_is_held(self):
        self.assertTrue(hold.should_hold_inference_only(self.root))

    def test_training_script_change_no_longer_matches_hold(self):
        (self.root / "scripts/train_gpt2_lora.py").write_bytes(b"different training recipe")
        self.assertFalse(hold.should_hold_inference_only(self.root))

    def test_notebook_or_dependency_change_no_longer_matches_hold(self):
        for path in ("kaggle/gpt2_training.ipynb", "requirements-kaggle.txt"):
            with self.subTest(path=path):
                target = self.root / path
                old = target.read_bytes()
                target.write_bytes(old + b" changed")
                self.assertFalse(hold.should_hold_inference_only(self.root))
                target.write_bytes(old)

    def test_train_or_eval_data_change_no_longer_matches_hold(self):
        for path in hold.EXPECTED_DATA_SHA256:
            with self.subTest(path=path):
                target = self.root / path
                old = target.read_bytes()
                target.write_bytes(old + b" changed")
                self.assertFalse(hold.should_hold_inference_only(self.root))
                target.write_bytes(old)

    def test_missing_file_is_not_mistaken_for_audited_snapshot(self):
        (self.root / "kaggle/gpt2_training.ipynb").unlink()
        self.assertFalse(hold.should_hold_inference_only(self.root))



class DailyScheduleCompatibilityTests(unittest.TestCase):
    """Do not silently revert the main-branch Daily schedule in this PR."""

    def test_preserves_deployed_schedule_and_serialization(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "daily-gpt2-training.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('cron: "17 1 * * *"', workflow)
        self.assertNotIn('cron: "0 1 * * *"', workflow)
        self.assertIn("group: daily-gpt2-training-canonical-kernel", workflow)
        self.assertIn("cancel-in-progress: false", workflow)


if __name__ == "__main__":
    unittest.main()
