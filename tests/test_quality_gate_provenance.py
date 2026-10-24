"""Offline regression: reused evidence must never masquerade as a new candidate.

Extracts the actual quality-gate Python from the workflow; no Kaggle, GPU,
credentials, model downloads, or repository checkpoint mutations are involved.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/daily-gpt2-training.yml"


def gate_code():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    step = workflow.split("- name: Candidate quality gate and approved-adapter promotion", 1)[1]
    embedded = step.split("python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    return textwrap.dedent(embedded)


class QualityGateProvenanceTests(unittest.TestCase):
    def evaluate(self, skipped, adapter):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run"
            output = run_dir / "kaggle_output" / "training_output"
            output.mkdir(parents=True)
            (output / "training_status.json").write_text(
                json.dumps({"status": "completed", "skipped_no_changes": skipped}),
                encoding="utf-8",
            )
            (output / "metrics.json").write_text(
                json.dumps({
                    "eval_loss_improvement_pct": 7.141,
                    "training_data_sha256": "test-train-sha",
                    "eval_data_sha256": "test-eval-sha",
                }), encoding="utf-8",
            )
            (output / "samples.json").write_text(
                json.dumps([{"output": "This is a meaningful example answer."}] * 10),
                encoding="utf-8",
            )
            if adapter:
                folder = output / "adapter"
                folder.mkdir()
                (folder / "adapter_config.json").write_text("{}", encoding="utf-8")
            env = dict(os.environ, RUN_DIR=str(run_dir), GITHUB_RUN_ID="123456")
            subprocess.run(
                [sys.executable, "-c", gate_code()],
                cwd=root, env=env, check=True, capture_output=True, text=True,
            )
            gate = json.loads((run_dir / "quality_gate.json").read_text(encoding="utf-8"))
            promoted = (root / "checkpoints" / "adapter_version.json").exists()
            return gate, promoted

    def test_reused_run_without_adapter_has_only_reuse_reason(self):
        gate, promoted = self.evaluate(skipped=True, adapter=False)
        self.assertFalse(gate["promotion_approved"])
        self.assertFalse(promoted)
        self.assertEqual(gate["candidate_status"], "skipped_no_changes")
        self.assertTrue(gate["evidence_reused"])
        self.assertIn("No new training candidate was created; prior evidence was reused.", gate["reasons"])
        self.assertNotIn("LoRA adapter files missing", gate["reasons"])

    def test_reused_run_with_adapter_never_promotes(self):
        gate, promoted = self.evaluate(skipped=True, adapter=True)
        self.assertFalse(gate["promotion_approved"])
        self.assertFalse(promoted)

    def test_real_completed_run_missing_adapter_is_rejected(self):
        gate, promoted = self.evaluate(skipped=False, adapter=False)
        self.assertFalse(gate["promotion_approved"])
        self.assertFalse(gate["evidence_reused"])
        self.assertEqual(gate["candidate_status"], "completed")
        self.assertIn("LoRA adapter files missing", gate["reasons"])
        self.assertFalse(promoted)

    def test_real_valid_candidate_preserves_promotion_path(self):
        gate, promoted = self.evaluate(skipped=False, adapter=True)
        self.assertTrue(gate["promotion_approved"])
        self.assertEqual(gate["reasons"], [])
        self.assertTrue(promoted)


if __name__ == "__main__":
    unittest.main()
