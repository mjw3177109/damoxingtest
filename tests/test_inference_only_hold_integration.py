"""CPU-only integration proof that the PR #72 snapshot cannot submit Kaggle."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from inference_only_submission_hold import should_hold_inference_only


class InferenceOnlyHoldIntegrationTests(unittest.TestCase):
    def test_audited_pr_snapshot_matches_exact_pin(self):
        self.assertTrue(should_hold_inference_only(ROOT))

    def test_pre_submit_guard_holds_without_generating_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "reports" / "run-test"
            output = root / "github_output"
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "pre_submit_reuse_guard.py"),
                 "--run-dir", str(run_dir), "--github-output", str(output)],
                cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("BLOCKED_INFERENCE_ONLY_CHANGE", result.stdout)
            self.assertIn("hold=true", output.read_text(encoding="utf-8"))
            self.assertIn("reuse=false", output.read_text(encoding="utf-8"))
            self.assertEqual(
                (run_dir / "status.txt").read_text(encoding="utf-8").strip(),
                "BLOCKED_INFERENCE_ONLY_CHANGE",
            )
            target = run_dir / "kaggle_output" / "training_output"
            status = json.loads((target / "training_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "blocked")
            self.assertFalse(status["kaggle_kernel_submitted"])
            self.assertFalse(status["current_run_performed_gpu_training"])
            self.assertFalse((target / "metrics.json").exists())
            self.assertFalse((target / "samples.json").exists())


if __name__ == "__main__":
    unittest.main()
