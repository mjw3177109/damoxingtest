"""Dependency-free fail-closed tests for Run 12 free-period CPU trajectory audit."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_free_period_trajectory import (
    MAX_NEW_TOKENS, describe_trajectory, longest_period_run, summarize,
)


def rows():
    return [{
        "phase": phase, "prompt_index": index,
        "input_history_sha256": f"fixed-history-{index}",
        "generated_token_count": 5, "period_token_count": 3,
        "unk_token_count": 0, "first_period_position": 1,
        "first_period_followed_by_period": True,
        "next_step_period_probability": 0.7, "next_step_period_rank": 1,
        "longest_period_run": 3, "stop_reason": "eos",
    } for phase in ("base", "candidate") for index in range(4)]


class FreePeriodTrajectoryTests(unittest.TestCase):
    def test_period_run_is_contiguous_not_total(self):
        self.assertEqual(longest_period_run([2, 2, 4, 2, 2, 2, 1], 2), 3)
        self.assertEqual(longest_period_run([1, 3, 4], 2), 0)

    def test_summary_requires_four_exact_paired_prompts(self):
        result = summarize(rows())
        self.assertEqual(result["base"]["period_seen"], 4)
        self.assertEqual(result["candidate"]["first_period_followed_by_period"], 4)
        self.assertEqual(result["candidate"]["max_period_streak"], 3)

    def test_missing_duplicate_and_mismatched_histories_fail_closed(self):
        for bad in (rows()[:-1], rows() + [rows()[0]]):
            with self.assertRaises(ValueError):
                summarize(bad)
        bad = rows()
        bad[-1]["input_history_sha256"] = "mismatch"
        with self.assertRaisesRegex(ValueError, "do not match"):
            summarize(bad)

    def test_invalid_metrics_are_rejected(self):
        for field, invalid in (
            ("generated_token_count", MAX_NEW_TOKENS + 1),
            ("period_token_count", -1),
            ("first_period_position", None),
            ("longest_period_run", 4),
            ("next_step_period_probability", float("nan")),
            ("next_step_period_rank", 0),
            ("first_period_followed_by_period", "yes"),
            ("unk_token_count", 99),
        ):
            bad = rows()
            bad[0][field] = invalid
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize(bad)

    def test_no_period_path_and_private_fields(self):
        result = describe_trajectory([3, 4, 5], [None] * 3, 2, 1, 0)
        self.assertIsNone(result["first_period_position"])
        self.assertIsNone(result["next_step_period_probability"])
        self.assertEqual(result["period_token_count"], 0)
        self.assertEqual(result["stop_reason"], "other")
        self.assertFalse({"token_ids", "prompt", "output", "logits"} & set(result))
        bad = rows()
        bad[0].update(first_period_position=None, period_token_count=0,
                      longest_period_run=0, first_period_followed_by_period=None,
                      next_step_period_probability=None, next_step_period_rank=None)
        self.assertEqual(summarize(bad)["base"]["period_seen"], 3)

    def test_empty_or_misaligned_generation_rejected(self):
        for ids, scores in (([], []), ([1, 2], [None]), ([1] * (MAX_NEW_TOKENS + 1), [None] * (MAX_NEW_TOKENS + 1))):
            with self.assertRaises(ValueError):
                describe_trajectory(ids, scores, 2, 1, 0)


if __name__ == "__main__":
    unittest.main()
