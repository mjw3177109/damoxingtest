import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from teacher_forced_token_probe import (
    FORCED_TOKENS, PROMPT_COUNT, STEPS, summarize, trace_fixed_prefix,
)


class TeacherForcedProbeTests(unittest.TestCase):
    def test_forced_history_is_not_model_argmax(self):
        histories = []
        def forward(history):
            histories.append(list(history))
            logits = [0.0] * 9000
            logits[119] = 2.0
            logits[7] = 5.0  # model would choose 7, but we force 119
            return logits
        rows = trace_fixed_prefix([1, 2], 119, forward, steps=3)
        self.assertEqual(histories, [[1, 2], [1, 2, 119], [1, 2, 119, 119]])
        self.assertEqual([r["forced_history_length"] for r in rows], [0, 1, 2])
        self.assertTrue(all(r["processed_top1_id"] == 7 for r in rows))

    def test_forced_alternative_history(self):
        histories = []
        def forward(history):
            histories.append(list(history))
            return [0.0] * 9000
        trace_fixed_prefix([1], 8601, forward, steps=3)
        self.assertEqual(histories, [[1], [1, 8601], [1, 8601, 8601]])

    def test_repetition_penalty_changes_watched_probability(self):
        def forward(_):
            logits = [0.0] * 9000
            logits[119] = 5.0
            return logits
        rows = trace_fixed_prefix([119], 119, forward, steps=2)
        self.assertLess(rows[0]["processed_token119_probability"], rows[0]["raw_token119_probability"])
        self.assertEqual(rows[0]["processed_token119_rank"], 1)

    def test_invalid_inputs_rejected(self):
        for args in (([], 119, 1), ([1], -1, 1), ([1], 119, 0), ([1], 119, 9)):
            with self.assertRaises(ValueError):
                trace_fixed_prefix(args[0], args[1], lambda _: [0.0] * 9000, steps=args[2])
        with self.assertRaises(ValueError):
            trace_fixed_prefix([1], 9001, lambda _: [0.0] * 9000, steps=1)

    def test_summary_requires_matching_conditions(self):
        results = []
        for phase in ("base", "candidate"):
            for index in range(PROMPT_COUNT):
                for forced in FORCED_TOKENS:
                    rows = [{
                        "step": step + 1,
                        "forced_history_length": step,
                        "processed_token119_probability": 0.2 if phase == "base" else 0.3,
                        "token119_is_top1": phase == "candidate",
                    } for step in range(STEPS)]
                    results.append({
                        "phase": phase, "prompt_index": index,
                        "forced_token_id": forced, "prompt_sha256": str(index),
                        "rows": rows,
                    })
        summary = summarize(results)
        self.assertEqual(len(summary), 2)
        self.assertTrue(all(s["matched_history_pairs"] == 32 for s in summary))
        self.assertTrue(all(s["candidate_higher_token119_probability"] == 32 for s in summary))
        results[-1]["prompt_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            summarize(results)


if __name__ == "__main__":
    unittest.main()
