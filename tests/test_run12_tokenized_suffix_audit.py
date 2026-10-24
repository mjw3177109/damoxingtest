"""Dependency-free tests for privacy-safe Run 12 tokenizer input parity."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_tokenized_suffix_audit import audit_records, compare_prompt, digest_ids, PROMPT_COUNT


class FakeTokenizer:
    def __init__(self, ignore_newline=False):
        self.ignore_newline = ignore_newline

    def __call__(self, prompt, add_special_tokens=True):
        assert add_special_tokens is True
        if self.ignore_newline:
            prompt = prompt.rstrip("\n")
        return {"input_ids": [101] + [ord(char) for char in prompt] + [102]}


class TokenizedSuffixTests(unittest.TestCase):
    def test_detects_no_effect_when_tokenizer_discards_trailing_newline(self):
        result = compare_prompt("用户：测试\n助手：", FakeTokenizer(ignore_newline=True))
        self.assertTrue(result["same_input_ids"])
        self.assertIsNone(result["first_differing_position"])
        self.assertEqual(result["control_token_sha256"], result["newline_token_sha256"])

    def test_detects_real_input_change(self):
        result = compare_prompt("用户：测试\n助手：", FakeTokenizer())
        self.assertFalse(result["same_input_ids"])
        self.assertEqual(result["newline_token_count"], result["control_token_count"] + 1)
        self.assertIsInstance(result["first_differing_position"], int)

    def test_fixed_prompt_count_and_no_raw_text_or_token_ids(self):
        records = [{"instruction": "固定问题" + str(i)} for i in range(PROMPT_COUNT)]
        result = audit_records(records, FakeTokenizer(ignore_newline=True))
        self.assertEqual(result["count"], PROMPT_COUNT)
        self.assertEqual(result["identical_tokenizations"], PROMPT_COUNT)
        self.assertEqual(result["different_tokenizations"], 0)
        text = str(result)
        self.assertNotIn("固定问题", text)
        self.assertNotIn("'input_ids':", text)
        self.assertNotIn("用户：", text)

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            compare_prompt("wrong", FakeTokenizer())
        with self.assertRaises(ValueError):
            digest_ids([])
        with self.assertRaises(ValueError):
            digest_ids([-1])
        with self.assertRaises(ValueError):
            audit_records([], FakeTokenizer())
        with self.assertRaises(ValueError):
            audit_records([{"instruction": None}] * PROMPT_COUNT, FakeTokenizer())


if __name__ == "__main__":
    unittest.main()
