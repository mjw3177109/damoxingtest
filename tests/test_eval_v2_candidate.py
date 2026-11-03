"""Versioned eval-v2 candidate integrity tests. No network/GPU required."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit_holdout_near_duplicates import audit, normalized, read_jsonl


class EvalV2CandidateTests(unittest.TestCase):
    def setUp(self):
        self.train = read_jsonl(ROOT / "data/safety_humanity_train_v2.jsonl")
        self.v1 = read_jsonl(ROOT / "data/safety_humanity_eval_v1.jsonl")
        self.v2 = read_jsonl(ROOT / "data/safety_humanity_eval_v2_candidate.jsonl")

    def test_versioned_minimal_change(self):
        self.assertEqual(len(self.v1), 24)
        self.assertEqual(len(self.v2), 24)
        changed = [i for i, (old, new) in enumerate(zip(self.v1, self.v2), 1) if old[1] != new[1]]
        self.assertEqual(changed, [19])
        self.assertEqual(self.v2[18][1]["source"], "fixed_holdout_v2_candidate")

    def test_no_exact_instruction_overlap(self):
        train = {normalized(row["instruction"]) for _, row in self.train}
        evals = [normalized(row["instruction"]) for _, row in self.v2]
        self.assertEqual(len(set(evals)), len(evals))
        self.assertTrue(train.isdisjoint(evals))

    def test_no_flagged_train_eval_near_duplicates(self):
        result = audit(self.train, self.v2)
        self.assertEqual(result["pair_count"], 2040)
        self.assertEqual(result["near_duplicate_pairs"], [])


if __name__ == "__main__":
    unittest.main()
