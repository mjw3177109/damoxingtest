"""Dependency-free checks for the 4-prompt train-parity decoding comparison."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_train_parity_bigram_cpu import summarize, verify_historical_control


def rows():
    result = []
    for phase in ("base", "candidate"):
        for setting in ("control", "no_repeat_bigram"):
            for i in range(4):
                is_candidate = phase == "candidate"
                is_control = setting == "control"
                period = 32 if is_candidate and is_control and i < 2 else 0
                unk = (32 if is_candidate and is_control and i == 3
                       else 1 if not is_candidate and is_control and i == 3 else 0)
                result.append({
                    "phase": phase, "setting": setting, "prompt_index": i,
                    "input_history_sha256": f"{i:064x}",
                    "generated_token_count": 32,
                    "period_count": period, "unk_count": unk,
                    "longest_period_run": period,
                    "stop_reason": "eos" if is_candidate and is_control and i == 2 else "max_new_tokens",
                    "punctuation_only": bool(period), "contains_chinese": False,
                })
    for row in result:
        if row["phase"] == "candidate" and row["setting"] == "control" and row["prompt_index"] == 2:
            row["generated_token_count"] = 27
    return result


class TrainParityBigramTests(unittest.TestCase):
    def test_valid_matched_controls(self):
        summary = summarize(rows())
        verify_historical_control(summary)
        self.assertEqual(summary["candidate/control"]["period_tokens"], 64)

    def test_missing_or_duplicate_fails(self):
        for bad in (rows()[:-1], rows() + [rows()[0]]):
            with self.assertRaisesRegex(ValueError, "16 distinct"):
                summarize(bad)

    def test_history_mismatch_fails(self):
        bad = rows()
        bad[-1]["input_history_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "histories differ"):
            summarize(bad)

    def test_raw_output_field_rejected(self):
        bad = rows()
        bad[0]["output"] = "private answer"
        with self.assertRaisesRegex(ValueError, "Unexpected fields"):
            summarize(bad)

    def test_invalid_metric_rejected(self):
        for field, value in (("generated_token_count", 33), ("unk_count", -1),
                             ("longest_period_run", 33), ("contains_chinese", 1)):
            bad = rows()
            bad[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize(bad)

    def test_historical_drift_fails(self):
        bad = rows()
        bad[0]["unk_count"] = 1
        with self.assertRaisesRegex(ValueError, "Base control differs"):
            verify_historical_control(summarize(bad))


if __name__ == "__main__":
    unittest.main()
