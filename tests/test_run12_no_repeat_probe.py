import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_no_repeat_probe import summarize, verify_historical_control


class NoRepeatProbeTests(unittest.TestCase):
    def make_rows(self):
        rows = []
        for phase in ("base", "candidate"):
            for setting in ("control", "no_repeat_bigram"):
                for index in range(10):
                    rows.append({"phase": phase, "setting": setting, "prompt_index": index,
                                 "punctuation_only": phase == "candidate" or index < 7,
                                 "stop_reason_inferred": "max_new_tokens",
                                 "longest_identical_character_run": 64})
        return rows

    def test_exact_pair_count(self):
        self.assertEqual(summarize(self.make_rows())["base/control"]["count"], 10)

    def test_duplicate_pair_rejected(self):
        rows = self.make_rows()
        rows[-1] = dict(rows[0])
        with self.assertRaisesRegex(ValueError, "40 distinct"):
            summarize(rows)

    def test_missing_pair_rejected(self):
        with self.assertRaisesRegex(ValueError, "40 distinct"):
            summarize(self.make_rows()[:-1])

    def test_control_parity(self):
        verify_historical_control(summarize(self.make_rows()))

    def test_control_drift_rejected(self):
        rows = self.make_rows()
        rows[0]["punctuation_only"] = False
        with self.assertRaisesRegex(ValueError, "diverges"):
            verify_historical_control(summarize(rows))


if __name__ == "__main__":
    unittest.main()
