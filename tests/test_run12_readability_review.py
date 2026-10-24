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

    def test_safe_excerpt_redacts_github_classic_token(self):
        self.assertIn("REDACTED", module.safe_excerpt("token=ghp_abcdefghijklmnop"))

    def test_safe_excerpt_redacts_github_fine_grained_token(self):
        self.assertIn("REDACTED", module.safe_excerpt("token=github_pat_abcdefghijklmnop"))

    def test_safe_excerpt_redacts_github_actions_token(self):
        self.assertIn("REDACTED", module.safe_excerpt("token=ghs_abcdefghijklmnop"))

    def test_safe_excerpt_redacts_openai_project_key(self):
        self.assertIn("REDACTED", module.safe_excerpt("key=sk-proj-abcdefgh12345678"))

    def test_safe_excerpt_checks_entire_text_before_truncating(self):
        output = "正常回答" * 60 + " ghp_abcdefghijklmnop"
        self.assertIn("REDACTED", module.safe_excerpt(output))

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



class SpecialTokenCategoryTests(unittest.TestCase):
    class FakeTokenizer:
        # EOS and SEP deliberately share an ID; raw IDs are never exported.
        all_special_ids = [11, 12, 13, 14, 15, 16, 17]
        unk_token_id = 11
        cls_token_id = 12
        mask_token_id = 13
        eos_token_id = 14
        sep_token_id = 14
        pad_token_id = 15
        bos_token_id = 16

        def decode(self, ids, skip_special_tokens=True):
            return "".join(
                "" if skip_special_tokens and token in self.all_special_ids
                else "[SPECIAL]" if token in self.all_special_ids
                else "好"
                for token in ids
            )

    def test_each_special_token_counted_once_even_with_aliases(self):
        ids = [11, 12, 13, 14, 15, 16, 17, 17, 99]
        counts = module.count_special_token_categories(ids, self.FakeTokenizer())
        self.assertEqual(sum(counts.values()), 8)
        self.assertEqual(counts["unk"], 1)
        self.assertEqual(counts["cls"], 1)
        self.assertEqual(counts["mask"], 1)
        self.assertEqual(counts["eos"], 1)
        self.assertEqual(counts["sep"], 0)
        self.assertEqual(counts["other_special"], 2)

    def test_all_unknown_special_tokens_produce_only_class_counts(self):
        ids = [11] * 64
        result = module.diagnose_decode_visibility(ids, self.FakeTokenizer())
        self.assertEqual(result["category"], "special_tokens_only")
        self.assertEqual(result["special_token_categories"]["unk"], 64)
        self.assertEqual(sum(result["special_token_categories"].values()), 64)
        self.assertNotIn("token_ids", result)
        self.assertNotIn("raw_ids", result)

    def test_regular_tokens_do_not_count_as_special(self):
        counts = module.count_special_token_categories([99, 99], self.FakeTokenizer())
        self.assertEqual(sum(counts.values()), 0)


if __name__ == "__main__":
    unittest.main()
