"""Dependency-free tests for the bounded token-changing prompt experiment."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_tokenized_direct_answer_audit import (
    PROMPT_COUNT, VARIANT_DIRECTIVE, audit_records, compare_prompt,
    token_digest, variant_prompt,
)


class FakeTokenizer:
    def __init__(self, ignore_directive=False):
        self.ignore_directive = ignore_directive

    def __call__(self, prompt, add_special_tokens=True):
        assert add_special_tokens is True
        if self.ignore_directive:
            prompt = prompt.replace("\n" + VARIANT_DIRECTIVE, "")
        return {"input_ids": [101] + [ord(ch) for ch in prompt] + [102]}


class TokenChangingVariantTests(unittest.TestCase):
    def test_one_directive_inserted_before_assistant(self):
        control = "用户：如何保护用户？\n助手："
        variant = variant_prompt(control)
        self.assertEqual(variant, "用户：如何保护用户？\n" + VARIANT_DIRECTIVE + "\n助手：")
        self.assertEqual(variant.count(VARIANT_DIRECTIVE), 1)

    def test_detects_real_token_change(self):
        row = compare_prompt("用户：测试\n助手：", FakeTokenizer())
        self.assertTrue(row["token_sequence_changed"])
        self.assertGreater(row["variant_token_count"], row["control_token_count"])
        self.assertIsInstance(row["first_differing_position"], int)

    def test_detects_inert_variant_and_does_not_claim_change(self):
        row = compare_prompt("用户：测试\n助手：", FakeTokenizer(ignore_directive=True))
        self.assertFalse(row["token_sequence_changed"])
        self.assertIsNone(row["first_differing_position"])

    def test_fixed_count_and_no_raw_prompts_or_ids_exported(self):
        records = [{"instruction": "隐私问题" + str(i)} for i in range(PROMPT_COUNT)]
        result = audit_records(records, FakeTokenizer())
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["changed_tokenizations"], 4)
        self.assertNotIn("隐私问题", str(result))
        self.assertNotIn("'input_ids':", str(result))
        self.assertNotIn(VARIANT_DIRECTIVE, str(result))

    def test_rejects_bad_templates_and_ids(self):
        for prompt in ("", "wrong", "用户：test\n系统："):
            with self.assertRaises(ValueError):
                variant_prompt(prompt)
        for ids in ([], [-1], [True]):
            with self.assertRaises(ValueError):
                token_digest(ids)
        with self.assertRaises(ValueError):
            audit_records([], FakeTokenizer())
        with self.assertRaises(ValueError):
            audit_records([{"instruction": ""}] * 4, FakeTokenizer())


if __name__ == "__main__":
    unittest.main()
