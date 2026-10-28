"""Offline safety contract for the Daily GPT-2 schedule experiment.

No network access, Kaggle credentials, model loading, or GPU usage.
"""
import re
import unittest
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github" / "workflows" / "daily-gpt2-training.yml"
)


class DailyScheduleSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_one_off_hour_daily_schedule(self):
        schedules = re.findall(
            r'^\s*-\s*cron:\s*["\']([^"\']+)["\']',
            self.workflow,
            flags=re.MULTILINE,
        )
        self.assertEqual(schedules, ["17 1 * * *"])

    def test_duplicate_training_guards_preserved(self):
        for contract in (
            "workflow_dispatch:",
            "group: daily-gpt2-training-canonical-kernel",
            "cancel-in-progress: false",
            "python tools/pre_submit_reuse_guard.py",
            'kaggle kernels status "$KERNEL_ID"',
            "promotion_approved",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.workflow)


if __name__ == "__main__":
    unittest.main()
