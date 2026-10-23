import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_matched_token_trajectories import compare, EXPECTED_SOURCE_RUN, EXPECTED_HOLDOUT_SHA256, EXPECTED_ADAPTER_SHA256


def fixture():
    rows = []
    for index in range(4):
        for phase in ("base", "candidate"):
            ids = [119, 119] if index != 1 or phase == "candidate" else [8601, 8601]
            rows.append({"prompt_index": index, "phase": phase, "prompt_sha256": f"hash{index}", "selected_token_ids": ids, "rows": [
                {"step": i + 1, "selected_token_id": t, "watch_probabilities": {"119": (0.3 if phase == "candidate" else 0.2)}}
                for i, t in enumerate(ids)
            ]})
    return {"source_training_run_id": EXPECTED_SOURCE_RUN, "holdout_sha256": EXPECTED_HOLDOUT_SHA256,
            "adapter_weights_sha256": EXPECTED_ADAPTER_SHA256,
            "first_step_parity": "matched audited Run 39975111441 on all 4 prompts and both models",
            "model_forward_passes": 16, "results": rows}


class MatchedTrajectoryTests(unittest.TestCase):
    def test_divergent_histories_not_compared(self):
        result = compare(fixture())
        self.assertEqual(result["matched_history_comparisons"], 7)
        self.assertEqual(result["prompts"][1]["matched_history_steps"], 1)
        self.assertEqual(result["prompts"][1]["first_divergence_after_step"], 1)
        self.assertEqual(result["positive_deltas"], 7)
        self.assertFalse(result["gpu_training_performed"])

    def test_rejects_wrong_evidence(self):
        data = fixture()
        data["adapter_weights_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            compare(data)

    def test_rejects_mismatched_prompts(self):
        data = fixture()
        data["results"][1]["prompt_sha256"] = "mismatch"
        with self.assertRaises(ValueError):
            compare(data)

    def test_rejects_malformed_trace(self):
        data = fixture()
        data["results"][0]["rows"][0]["watch_probabilities"]["119"] = float("nan")
        with self.assertRaises(ValueError):
            compare(data)


if __name__ == "__main__":
    unittest.main()
