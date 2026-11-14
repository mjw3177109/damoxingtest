"""Offline tests for read-only paired Artifact diagnostics."""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from paired_reference_diagnostics import summarize_pairs


def rows():
    out = []
    for i in range(10):
        for arm in ("base", "run12_candidate"):
            out.append({
                "arm": arm, "prompt_index": i,
                "prompt_sha256": hashlib.sha256(str(i).encode()).hexdigest(),
                "char_bigram_f1": 0.1,
                "output_char_count": 64,
                "stop_reason_inferred": "max_new_tokens",
            })
    return out


class PairedReferenceTests(unittest.TestCase):
    def test_ties_and_changed_lengths(self):
        values = rows()
        values[1]["output_char_count"] = 13
        values[1]["stop_reason_inferred"] = "eos"
        result = summarize_pairs(values)
        self.assertEqual(result["tied_bigram_f1"], 10)
        self.assertEqual(result["output_character_length_changed"], 1)
        self.assertEqual(result["eos_status_changed"], 1)
        self.assertFalse(result["promotion_approved"])

    def test_mixed_wins_losses(self):
        values = rows()
        values[1]["char_bigram_f1"] = 0.2
        values[3]["char_bigram_f1"] = 0.05
        result = summarize_pairs(values)
        self.assertEqual((result["candidate_better_bigram_f1"], result["candidate_worse_bigram_f1"], result["tied_bigram_f1"]), (1, 1, 8))

    def test_reject_duplicate_or_missing(self):
        with self.assertRaises(ValueError):
            summarize_pairs(rows()[:-1])
        values = rows()
        values[1]["prompt_index"] = 1
        with self.assertRaises(ValueError):
            summarize_pairs(values)

    def test_reject_unpaired_and_invalid_numbers(self):
        values = rows()
        values[1]["prompt_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            summarize_pairs(values)
        values = rows()
        values[0]["char_bigram_f1"] = float("nan")
        with self.assertRaises(ValueError):
            summarize_pairs(values)
        values = rows()
        values[0]["output_char_count"] = -1
        with self.assertRaises(ValueError):
            summarize_pairs(values)


if __name__ == "__main__":
    unittest.main()
