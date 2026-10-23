import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from first_token_probability_probe import summarize_logits


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


if __name__ == "__main__":
    unittest.main()
