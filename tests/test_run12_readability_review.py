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



class DecodeVisibilityTests(unittest.TestCase):
    class FakeTokenizer:
        all_special_ids = [0]
        eos_token_id = 0
        pad_token_id = 0

        def decode(self, ids, skip_special_tokens=True):
            mapping = {0: "[SEP]", 1: " ", 2: "好", 3: ""}
            return "".join(
                "" if token == 0 and skip_special_tokens else mapping[token]
                for token in ids
            )

    def setUp(self):
        self.tokenizer = self.FakeTokenizer()

    def test_all_special_tokens_explain_blank(self):
        result = module.diagnose_decode_visibility([0] * 64, self.tokenizer)
        self.assertEqual(result["category"], "special_tokens_only")
        self.assertEqual(result["special_token_count"], 64)
        self.assertEqual(result["eos_token_count"], 64)
        self.assertEqual(result["stripped_decode_length"], 0)

    def test_whitespace_only_explains_stripped_blank(self):
        result = module.diagnose_decode_visibility([1] * 64, self.tokenizer)
        self.assertEqual(result["category"], "whitespace_only")
        self.assertEqual(result["filtered_whitespace_count"], 64)
        self.assertEqual(result["special_token_count"], 0)

    def test_visible_chinese_is_not_blank(self):
        result = module.diagnose_decode_visibility([2, 0], self.tokenizer)
        self.assertEqual(result["category"], "visible_text")
        self.assertEqual(result["stripped_decode_length"], 1)

    def test_empty_generation_is_distinct(self):
        result = module.diagnose_decode_visibility([], self.tokenizer)
        self.assertEqual(result["category"], "no_generated_tokens")

    def test_filtered_non_special_ids_are_distinct(self):
        result = module.diagnose_decode_visibility([3] * 64, self.tokenizer)
        self.assertEqual(result["category"], "decoder_filtered_all")
        self.assertEqual(result["special_token_count"], 0)

    def test_no_raw_text_or_token_ids_in_report(self):
        result = module.diagnose_decode_visibility([2, 0], self.tokenizer)
        self.assertNotIn("token_ids", result)
        self.assertNotIn("output", result)
        self.assertNotIn("好", str(result))



if __name__ == "__main__":
    unittest.main()
