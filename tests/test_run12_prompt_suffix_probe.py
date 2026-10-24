"""Offline, dependency-light contract tests for Run 12 prompt suffix sensitivity."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run12_prompt_suffix_probe import variant_prompt, verify_production_parity, summarize, PHASES, SETTINGS, PROMPT_COUNT


class PromptSuffixTests(unittest.TestCase):
    def test_training_and_generation_templates_already_match(self):
        self.assertTrue(verify_production_parity(ROOT / "scripts/train_gpt2_lora.py"))

    def test_single_variable_suffix(self):
        prompt = "用户：请先核实数据。\n助手："
        self.assertEqual(variant_prompt(prompt, "train_parity"), prompt)
        self.assertEqual(variant_prompt(prompt, "assistant_newline"), prompt + "\n")

    def test_reject_unknown_template_or_bad_prefix(self):
        for prompt, setting in [("bad", "train_parity"),
                                ("用户：你好\n助手：", "unknown")]:
            with self.assertRaises(ValueError):
                variant_prompt(prompt, setting)

    @staticmethod
    def rows():
        return [
            {"phase": phase, "setting": setting, "prompt_index": i,
             "instruction_sha256": str(i),
             "punctuation_only": setting == "train_parity",
             "contains_chinese": setting == "assistant_newline",
             "stop_reason_inferred": "eos" if setting == "assistant_newline" else "max_new_tokens",
             "decode_visibility": {"stripped_decode_length": 1},
             "first_step_unk": {"processed": {"unk_rank": 1 if setting == "train_parity" else 3,
                                              "unk_probability": .2 if setting == "train_parity" else .1}}}
            for phase in PHASES for setting in SETTINGS for i in range(PROMPT_COUNT)
        ]

    def test_summary_counts_and_pairing(self):
        result = summarize(self.rows())
        self.assertEqual(result["candidate/train_parity"]["punctuation_only"], 4)
        self.assertEqual(result["candidate/assistant_newline"]["contains_chinese"], 4)
        self.assertEqual(result["base/assistant_newline"]["eos"], 4)
        self.assertEqual(result["candidate/train_parity"]["unk_first_top1"], 4)

    def test_reject_duplicate_or_missing_or_mismatched(self):
        rows = self.rows()
        for broken in (rows[:-1], rows + [rows[0]]):
            with self.assertRaises(ValueError):
                summarize(broken)
        rows[-1]["instruction_sha256"] = "mismatch"
        with self.assertRaises(ValueError):
            summarize(rows)

    def test_no_raw_token_ids_or_prompts_in_summary(self):
        summary = summarize(self.rows())
        self.assertNotIn("token_ids", str(summary))
        self.assertNotIn("prompt", str(summary))


if __name__ == "__main__":
    unittest.main()
