"""Offline validation for exact-input base vs candidate lexical/length audit."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_train_exact_reference_cpu import ARMS, ROW_FIELDS, measure, summarize


def paired_rows():
    rows = []
    for arm in ARMS:
        for i in range(10):
            rows.append({
                "arm": arm, "prompt_index": i,
                "prompt_sha256": f"{i + 1:064x}",
                "generated_token_count": 15,
                "eos_position": 14,
                "stop_reason_inferred": "eos",
                "character_count": 10,
                "distinct_characters": 8,
                "longest_identical_character_run": 2,
                "punctuation_only": False,
                "char_bigram_f1": 0.125 if arm == "base" else 0.25,
                "output_char_count": 10,
                "cjk_char_count": 8,
                "empty_output": False,
                "reference_char_count": 40,
                "output_to_reference_char_ratio": 0.25,
                "short_relative_to_reference": False,
            })
    return rows


class ExactReferenceTests(unittest.TestCase):
    def test_measure_shortness_and_lexical_overlap(self):
        x = measure("安全", "安全原则应先验证再部署")
        self.assertGreater(x["char_bigram_f1"], 0)
        self.assertTrue(x["short_relative_to_reference"])
        self.assertEqual(x["output_char_count"], 2)

    def test_summary_paired_comparison(self):
        result = summarize(paired_rows())
        self.assertEqual(result["base"]["samples"], 10)
        self.assertEqual(result["run12_candidate"]["eos_count"], 10)
        self.assertEqual(result["candidate_minus_base_bigram_f1"], 0.125)
        self.assertIsNone(result["run12_candidate"]["direct_answer_count"])

    def test_reject_raw_text_fields(self):
        rows = paired_rows()
        rows[0]["output"] = "unredacted"
        with self.assertRaisesRegex(ValueError, "privacy-unsafe"):
            summarize(rows)

    def test_reject_raw_token_ids(self):
        rows = paired_rows()
        rows[0]["token_ids"] = [1, 2]
        with self.assertRaisesRegex(ValueError, "privacy-unsafe"):
            summarize(rows)

    def test_reject_missing_and_duplicate_rows(self):
        with self.assertRaisesRegex(ValueError, "Expected exactly"):
            summarize(paired_rows()[:-1])
        rows = paired_rows()
        rows[-1]["prompt_index"] = 0
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            summarize(rows)

    def test_reject_unpaired_prompts(self):
        rows = paired_rows()
        rows[-1]["prompt_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "Unpaired"):
            summarize(rows)


if __name__ == "__main__":
    unittest.main()
