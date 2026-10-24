"""Offline tests for bounded and privacy-filtered Run 12 review."""
import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("run12_readability_review", TOOLS / "run12_readability_review.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReadabilityReviewTests(unittest.TestCase):
    def test_safe_excerpt_retains_chinese(self):
        self.assertEqual(module.safe_excerpt("您好，请先核实。"), "您好，请先核实。")

    def test_safe_excerpt_redacts_email(self):
        self.assertIn("REDACTED", module.safe_excerpt("联系 foo@example.com"))

    def test_safe_excerpt_redacts_credentials(self):
        self.assertIn("REDACTED", module.safe_excerpt("ghp-abcdefghijklmnop"))

    def test_safe_excerpt_redacts_url(self):
        self.assertIn("REDACTED", module.safe_excerpt("https://example.com"))

    def test_safe_excerpt_bounded(self):
        self.assertLessEqual(len(module.safe_excerpt("好" * 200)), 161)

    def test_rejects_missing_pair(self):
        with self.assertRaisesRegex(ValueError, "eight"):
            module.summarize([])

    def test_valid_pair_summary(self):
        rows = [{"phase": p, "prompt_index": i, "punctuation_only": False,
                 "safe_output_excerpt": "中文", "stop_reason_inferred": "eos"}
                for p in ("base", "candidate") for i in range(4)]
        result = module.summarize(rows)
        self.assertEqual(result["candidate"]["contains_chinese"], 4)
        self.assertTrue(result["base"]["manual_review_required"])


if __name__ == "__main__":
    unittest.main()
