"""Offline tests for bounded first-step category probability experiment."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_first_step_category_cpu import category_ids, measure_categories, summarize

class FakeTokenizer:
    unk_token_id = 0
    eos_token_id = 1
    def encode(self, char, add_special_tokens=False):
        return {".": [2], "。": [3], "!": [0]}.get(char, [4, 5])

class CategoryProbeTests(unittest.TestCase):
    def test_categories_skip_unk_and_multitoken(self):
        self.assertEqual(category_ids(FakeTokenizer(), 6),
                         {"unk": {0}, "eos": {1}, "punctuation": {2, 3}})

    def test_softmax_categories_and_ranks(self):
        categories = {"unk": {0}, "eos": {1}, "punctuation": {2, 3}}
        result = measure_categories([0., 1., 3., 2., -1.], categories)
        self.assertEqual(result["top1_category"], "punctuation")
        self.assertEqual(result["punctuation_best_rank"], 1)
        self.assertEqual(result["unk_best_rank"], 4)
        self.assertNotIn("token_id", result)

    def test_reject_nonfinite_and_overlaps(self):
        cats = {"unk": {0}, "eos": {1}, "punctuation": {2}}
        for logits in ([], [0., float("nan"), 1.], [0., float("inf"), 1.]):
            with self.assertRaises(ValueError):
                measure_categories(logits, cats)
        with self.assertRaises(ValueError):
            measure_categories([0., 1., 2.], {"unk": {0}, "eos": {0}, "punctuation": {2}})

    def test_summary_exact_pairs_and_privacy(self):
        rows = []
        for phase in ("base", "candidate"):
            for setting in ("control", "direct_answer"):
                for index in range(4):
                    rows.append({"phase": phase, "setting": setting, "prompt_index": index,
                                 "prompt_sha256": setting + str(index),
                                 "processed": {"unk_probability": .1 if setting == "control" else .2,
                                               "eos_probability": .2, "punctuation_probability": .3,
                                               "top1_category": "other"}})
        result = summarize(rows)
        self.assertEqual(result["paired_comparisons"], 8)
        self.assertAlmostEqual(result["mean_variant_minus_control"]["base"]["unk"], .1)
        with self.assertRaises(ValueError):
            summarize(rows[:-1])
        with self.assertRaises(ValueError):
            summarize(rows + [rows[0]])
        rows[-1]["prompt_sha256"] = "control3"
        with self.assertRaises(ValueError):
            summarize(rows)

if __name__ == "__main__":
    unittest.main()
