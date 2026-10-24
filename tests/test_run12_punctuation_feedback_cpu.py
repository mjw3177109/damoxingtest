"""Offline safety and matching tests for forced-punctuation CPU audit."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_punctuation_feedback_cpu import summarize


def make_rows():
    rows = []
    for phase in ("base", "candidate"):
        for index in range(4):
            for count in range(4):
                rows.append({
                    "phase": phase,
                    "prompt_index": index,
                    "forced_punctuation_count": count,
                    "history_sha256": f"history-{index}-{count}",
                    "processed": {
                        "top1_category": "punctuation" if phase == "candidate" and count else "other",
                        "punctuation_probability": 0.4 if phase == "candidate" else 0.2,
                        "unk_probability": 0.1,
                        "eos_probability": 0.05,
                    },
                })
    return rows


class PunctuationFeedbackTests(unittest.TestCase):
    def test_exact_matched_pairs_and_delta(self):
        result = summarize(make_rows())
        self.assertEqual(result["matched_pairs"], 16)
        self.assertEqual(result["punctuation_top1_by_forced_count"]["base"]["3"], 0)
        self.assertEqual(result["punctuation_top1_by_forced_count"]["candidate"]["3"], 4)
        self.assertAlmostEqual(
            result["candidate_minus_base_mean_punctuation_probability_by_forced_count"]["2"], 0.2)

    def test_missing_or_duplicate_rows_rejected(self):
        rows = make_rows()
        with self.assertRaises(ValueError):
            summarize(rows[:-1])
        with self.assertRaises(ValueError):
            summarize(rows + [rows[0]])

    def test_unmatched_histories_rejected(self):
        rows = make_rows()
        rows[-1]["history_sha256"] = "different-history"
        with self.assertRaisesRegex(ValueError, "Unmatched"):
            summarize(rows)

    def test_invalid_probability_rejected(self):
        for bad in (-0.1, 1.01, float("nan")):
            rows = make_rows()
            rows[0]["processed"]["punctuation_probability"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                summarize(rows)


if __name__ == "__main__":
    unittest.main()
