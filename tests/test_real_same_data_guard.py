"""Read-only regression against the archived Run 12 training provenance.

No Kaggle credentials, network access, model loading, or GPU required.
This test exercises the real historical data fingerprint rather than only
synthetic fixtures. If the corpus is intentionally versioned forward,
the old-run comparison becomes inapplicable and is skipped.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pre_submit_reuse_guard as guard


class RealHistoricalSameDataGuardTests(unittest.TestCase):
    def test_run12_recipe_only_change_does_not_submit_gpu(self):
        source = ROOT / "reports/2026-10-23/run-39921870784"
        metadata_path = source / "run_metadata.json"
        status_path = source / "training_status.json"
        train = ROOT / "data/safety_humanity_train_v2.jsonl"
        holdout = ROOT / "data/safety_humanity_eval_v1.jsonl"
        for path in (metadata_path, status_path, train, holdout):
            self.assertTrue(path.is_file(), f"Required real provenance missing: {path.name}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        status = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertEqual(status.get("status"), "completed")
        self.assertFalse(status.get("skipped_no_changes", False))
        current_train_sha = hashlib.sha256(train.read_bytes()).hexdigest()
        current_eval_sha = hashlib.sha256(holdout.read_bytes()).hexdigest()
        if (metadata.get("training_data_sha256") != current_train_sha
                or metadata.get("eval_data_sha256") != current_eval_sha):
            self.skipTest("Corpus changed since Run 12; historical same-data guard not applicable")
        self.assertTrue(guard.has_completed_same_data_run(
            "data/safety_humanity_train_v2.jsonl",
            "data/safety_humanity_eval_v1.jsonl",
        ))
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-recipe-only-change"
            output = Path(tmp) / "github-output.txt"
            argv = ["guard", "--run-dir", str(run_dir), "--github-output", str(output)]
            # A changed guard implementation changes the legacy recipe hash:
            # exact reuse fails, but same-data training must remain blocked.
            with patch.object(sys, "argv", argv), patch.object(
                guard, "find_reusable_run", return_value=None
            ):
                guard.main()
            self.assertIn("blocked=true", output.read_text(encoding="utf-8"))
            self.assertIn("reuse=false", output.read_text(encoding="utf-8"))
            self.assertEqual(
                (run_dir / "status.txt").read_text(encoding="utf-8").strip(),
                "BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL",
            )
            decision = json.loads(
                (run_dir / "reuse_guard_decision.json").read_text(encoding="utf-8")
            )
            self.assertIs(decision.get("kaggle_kernel_submitted"), False)
            self.assertFalse((run_dir / "kaggle_output").exists())


if __name__ == "__main__":
    unittest.main()
