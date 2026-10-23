import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from conditional_token_probe import adjust_repetition, trace_greedy, token_probability, extend_token_types


class ConditionalTokenProbeTests(unittest.TestCase):
    def test_penalty_sign_and_dedup(self):
        self.assertEqual(adjust_repetition([4.0, -2.0, 1.0], [0, 0, 1], 2), [2.0, -4.0, 1.0])

    def test_repeated_token_and_bounded_steps(self):
        trace = trace_greedy([0], lambda history: [0.0, 5.0], steps=3)
        self.assertEqual(trace["selected_token_ids"], [1, 1, 1])
        self.assertTrue(trace["same_token_all_steps"])
        self.assertEqual([r["same_as_previous_generated"] for r in trace["rows"]], [False, True, True])
        self.assertEqual(trace["stop_reason"], "bounded_steps")

    def test_eos_stops_early(self):
        trace = trace_greedy([0], lambda history: [0.0, 2.0], eos_ids=(1,))
        self.assertEqual(trace["steps_executed"], 1)
        self.assertEqual(trace["stop_reason"], "eos")

    def test_history_updates_each_step(self):
        seen = []
        def forward(history):
            seen.append(tuple(history))
            return [0.0, 3.0, 2.0] if len(history) == 1 else [0.0, 0.0, 4.0]
        trace = trace_greedy([0], forward, steps=2)
        self.assertEqual(seen, [(0,), (0, 1)])
        self.assertEqual(trace["selected_token_ids"], [1, 2])

    def test_token_type_history_is_preserved(self):
        self.assertEqual(extend_token_types([0, 0, 1], 5), [0, 0, 1, 1, 1])
        self.assertIsNone(extend_token_types(None, 4))
        with self.assertRaises(ValueError):
            extend_token_types([0, 1], 1)

    def test_probability_and_invalid_inputs(self):
        self.assertAlmostEqual(token_probability([1000, 999], 0), 1/(1+math.exp(-1)))
        for history, steps in (([], 2), ([0], 0), ([0], 9)):
            with self.assertRaises(ValueError):
                trace_greedy(history, lambda x: [0, 1], steps=steps)
        with self.assertRaises(ValueError):
            adjust_repetition([1.0], [3])
        with self.assertRaises(ValueError):
            adjust_repetition([float("nan")], [0])


if __name__ == "__main__":
    unittest.main()
