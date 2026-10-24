"""Offline fail-closed tests for the bounded single-period CPU audit."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_period_token_cpu import measure_token, summarize


def rows():
    output = []
    for phase in ("base", "candidate"):
        for index in range(4):
            for count in range(4):
                output.append({
                    "phase": phase, "prompt_index": index, "forced_period_count": count,
                    "history_sha256": f"fixed-{index}-{count}",
                    "raw": {"period_probability": 0.3, "period_rank": 1, "period_top1": True,
                            "unk_probability": 0.1, "unk_rank": 2, "eos_probability": 0.05, "eos_rank": 3},
                    "processed": {"period_probability": 0.3 if phase == "candidate" else 0.2,
                                  "period_rank": 1 if phase == "candidate" else 2,
                                  "period_top1": phase == "candidate",
                                  "unk_probability": 0.1, "unk_rank": 3,
                                  "eos_probability": 0.05, "eos_rank": 4},
                })
    return output


class PeriodTokenAuditTests(unittest.TestCase):
    def test_stable_probability_and_rank(self):
        measured = measure_token([1.0, 3.0, 2.0, 0.0], 1, 2, 3)
        self.assertEqual(measured["period_rank"], 1)
        self.assertTrue(measured["period_top1"])
        self.assertAlmostEqual(measured["period_probability"], 0.64391426, places=7)
        self.assertEqual(measure_token([1.0, 1.0, 0.0], 1, 0, 2)["period_rank"], 2)

    def test_exact_paired_summary(self):
        result = summarize(rows())
        self.assertEqual(result["matched_pairs"], 16)
        self.assertEqual(result["period_top1_by_forced_count"]["base"]["1"], 0)
        self.assertEqual(result["period_top1_by_forced_count"]["candidate"]["1"], 4)

    def test_missing_duplicate_and_mismatched_histories_rejected(self):
        data = rows()
        with self.assertRaises(ValueError):
            summarize(data[:-1])
        with self.assertRaises(ValueError):
            summarize(data + [data[0]])
        data[-1]["history_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "Mismatched"):
            summarize(data)

    def test_invalid_probability_rank_or_top1_rejected(self):
        for key, value in (("period_probability", float("nan")),
                           ("unk_probability", -0.1), ("period_rank", 0),
                           ("period_top1", True)):
            data = rows()
            data[0]["processed"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                summarize(data)
        with self.assertRaises(ValueError):
            measure_token([1.0, float("inf"), 0.0], 0, 1, 2)
        with self.assertRaises(ValueError):
            measure_token([1.0, 2.0, 0.0], 0, 0, 2)


if __name__ == "__main__":
    unittest.main()
