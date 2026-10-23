import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from first_token_probability_probe import summarize_logits, apply_repetition_penalty


class FirstTokenProbabilityTests(unittest.TestCase):
    def test_topk_and_watch_ranks(self):
        result = summarize_logits([0.0, 2.0, 1.0], watch_ids=(0, 1, 2), top_k=2)
        self.assertEqual([x["token_id"] for x in result["top_k"]], [1, 2])
        self.assertEqual(result["watch"]["1"]["rank"], 1)
        self.assertGreater(result["watch"]["1"]["probability"], result["watch"]["2"]["probability"])
        self.assertAlmostEqual(
            sum(result["watch"][str(i)]["probability"] for i in range(3)), 1.0, places=7
        )
        self.assertGreater(result["entropy_nats"], 0)

    def test_large_logits_are_numerically_stable(self):
        result = summarize_logits([1000000.0, 999999.0], watch_ids=(0, 1))
        self.assertEqual(result["top_k"][0]["token_id"], 0)
        self.assertTrue(math.isfinite(result["entropy_nats"]))

    def test_invalid_logits_are_rejected(self):
        for values in ([], [float("nan")], [float("inf")]):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    summarize_logits(values)
        with self.assertRaises(ValueError):
            summarize_logits([1.0], top_k=0)

    def test_out_of_range_watch_id_not_recorded(self):
        result = summarize_logits([0.0, 0.0], watch_ids=(119, 0), top_k=5)
        self.assertEqual(list(result["watch"]), ["0"])
        self.assertEqual(len(result["top_k"]), 2)

    def test_repetition_penalty_matches_sign_rule(self):
        adjusted = apply_repetition_penalty([2.0, -2.0, 3.0], [0, 1], penalty=2.0)
        self.assertEqual(adjusted, [1.0, -4.0, 3.0])

    def test_repeated_prompt_token_is_penalized_once(self):
        self.assertEqual(
            apply_repetition_penalty([4.0, 2.0], [0, 0, 0], penalty=2.0),
            [2.0, 2.0],
        )

    def test_first_step_rank_can_change(self):
        raw = [2.0, 1.9]
        adjusted = apply_repetition_penalty(raw, [0], penalty=1.12)
        self.assertEqual(summarize_logits(raw, watch_ids=(0, 1))["top_k"][0]["token_id"], 0)
        self.assertEqual(summarize_logits(adjusted, watch_ids=(0, 1))["top_k"][0]["token_id"], 1)

    def test_repetition_penalty_invalid_input(self):
        for penalty in (0, -1, float("nan"), float("inf")):
            with self.subTest(penalty=penalty), self.assertRaises(ValueError):
                apply_repetition_penalty([1.0], [0], penalty)
        with self.assertRaises(ValueError):
            apply_repetition_penalty([1.0], [2])
        with self.assertRaises(ValueError):
            apply_repetition_penalty([float("nan")], [0])


if __name__ == "__main__":
    unittest.main()
