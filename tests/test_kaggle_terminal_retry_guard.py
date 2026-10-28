"""Offline guard against repeated GPU spending after a terminal Kaggle failure.

No network, credentials, Kaggle CLI, GPU or model weights are required.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-gpt2-training.yml"


class TerminalKaggleRetryGuardTests(unittest.TestCase):
    def test_preserves_deployed_non_top_of_hour_daily_schedule(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "17 1 * * *"', workflow)
        self.assertNotIn('cron: "0 1 * * *"', workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_terminal_failure_requires_review_instead_of_gpu_push(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        marker = 'KernelWorkerStatus\\.(ERROR|FAILED|CANCELLED)'
        self.assertIn(marker, workflow)
        terminal_branch = workflow.split(marker, 1)[1].split("\n            else", 1)[0]
        self.assertIn('echo "KAGGLE_RETRY_REQUIRES_REVIEW" > "$RUN_DIR/status.txt"', terminal_branch)
        self.assertIn("refusing automatic GPU retry", terminal_branch)
        self.assertIn("exit 0", terminal_branch)
        self.assertNotIn('NEED_PUSH="true"', terminal_branch)
        self.assertIn('NEED_PUSH="true"', workflow)  # existing COMPLETE / first-run paths retained
        self.assertIn('cancel-in-progress: false', workflow)

    def test_review_required_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "status.txt").write_text(
                "KAGGLE_RETRY_REQUIRES_REVIEW\n", encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "finalize_report.py"),
                 "--run-dir", str(run_dir)],
                cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (run_dir / "final_status.txt").read_text(encoding="utf-8").strip(),
                "KAGGLE_RETRY_REQUIRES_REVIEW",
            )
            self.assertIn("KAGGLE_RETRY_REQUIRES_REVIEW",
                          (run_dir / "report.md").read_text(encoding="utf-8"))
            self.assertFalse((run_dir / "metrics.json").exists())
            self.assertFalse((run_dir / "samples.json").exists())


if __name__ == "__main__":
    unittest.main()
