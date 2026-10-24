"""Offline tests for bounded Run 12 UNK fixed-prefix probe."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_unk_fixed_prefix_probe import compare_pairs, measure_unk, PROMPTS, STEPS


class UnkFixedPrefixTests(unittest.TestCase):
    def test_probability_and_repetition_penalty(self):
        stats = measure_unk([1.0, 4.0, 2.0], [0, 1], unk_id=1)
        self.assertEqual(stats["raw"]["unk_rank"], 1)
        self.assertLess(stats["processed"]["unk_logit"], stats["raw"]["unk_logit"])
        self.assertTrue(0 < stats["processed"]["unk_probability"] < 1)

    def test_no_raw_tokens_in_summary(self):
        stats = measure_unk([1.0, 2.0, 3.0], [0], unk_id=2)
        self.assertEqual(set(stats), {"raw", "processed"})
        self.assertEqual(set(stats["raw"]),
                         {"unk_logit", "unk_probability", "unk_rank", "unk_margin_to_top1", "unk_is_top1"})

    def test_invalid_logits_and_history_rejected(self):
        for logits, history, unk in [([], [0], 0), ([1.0, float("nan")], [0], 0),
                                      ([1.0], [], 0), ([1.0], [2], 0), ([1.0], [0], 2)]:
            with self.assertRaises(ValueError):
                measure_unk(logits, history, unk)

    @staticmethod
    def sample_rows():
        return [
            {"phase": phase, "prompt_index": i, "forced_unk_count": step,
             "prompt_sha256": str(i),
             "statistics": {"processed": {"unk_probability": .1 if phase == "base" else .2,
                                          "unk_rank": 2 if phase == "base" else 1,
                                          "unk_is_top1": phase == "candidate"}}}
            for phase in ("base", "candidate") for i in range(PROMPTS) for step in range(STEPS)
        ]

    def test_exact_matched_pairs(self):
        result = compare_pairs(self.sample_rows())
        self.assertEqual(result["matched_pairs"], 20)
        self.assertEqual(result["candidate_higher_unk_probability"], 20)
        self.assertEqual(result["candidate_unk_top1_count"], 20)
        self.assertEqual(len(result["blank_prompt_pairs"]), STEPS)

    def test_missing_duplicate_and_mismatch_rejected(self):
        rows = self.sample_rows()
        with self.assertRaises(ValueError):
            compare_pairs(rows[:-1])
        with self.assertRaises(ValueError):
            compare_pairs(rows + [rows[0]])
        rows[-1]["prompt_sha256"] = "mismatch"
        with self.assertRaises(ValueError):
            compare_pairs(rows)

    def test_invalid_probabilities_rejected(self):
        rows = self.sample_rows()
        rows[0]["statistics"]["processed"]["unk_probability"] = float("nan")
        with self.assertRaises(ValueError):
            compare_pairs(rows)


if __name__ == "__main__":
    unittest.main()
