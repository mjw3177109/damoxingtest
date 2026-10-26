"""Offline regression: reused evidence must never masquerade as a new candidate.

Extracts the actual quality-gate Python from the workflow; no Kaggle, GPU,
credentials, model downloads, or repository checkpoint mutations are involved.
"""
import hashlib
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
    def evaluate(self, skipped, adapter, workflow_status=None, train_sha_override=None,
                 eval_sha_override=None, recipe_sha_override=None, missing_metadata=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run"
            output = run_dir / "kaggle_output" / "training_output"
            output.mkdir(parents=True)
            if workflow_status != "__MISSING__":
                current_status = workflow_status or ("PRE_SUBMIT_SKIPPED_NO_CHANGES" if skipped else "COMPLETE")
                (run_dir / "status.txt").write_text(current_status + "\n", encoding="utf-8")
            (output / "training_status.json").write_text(
                json.dumps({"status": "completed", "skipped_no_changes": skipped}),
                encoding="utf-8",
            )
            # Mirror the real training fingerprint contract without network/GPU.
            (root / "data").mkdir()
            (root / "scripts").mkdir()
            (root / "kaggle").mkdir()
            train = root / "data/safety_humanity_train_v2.jsonl"
            holdout = root / "data/safety_humanity_eval_v1.jsonl"
            train.write_text('{"instruction":"A","response":"B"}\n', encoding="utf-8")
            holdout.write_text('{"instruction":"C","response":"D"}\n', encoding="utf-8")
            recipe = hashlib.sha256()
            for relative in ("scripts/train_gpt2_lora.py", "kaggle/gpt2_training.ipynb",
                             "requirements-kaggle.txt"):
                file = root / relative
                file.write_text("fixture", encoding="utf-8")
                recipe.update(relative.encode("utf-8"))
                recipe.update(file.read_bytes())
            evidence = {
                "training_data_sha256": train_sha_override or hashlib.sha256(train.read_bytes()).hexdigest(),
                "eval_data_sha256": eval_sha_override or hashlib.sha256(holdout.read_bytes()).hexdigest(),
                "training_recipe_sha256": recipe_sha_override or recipe.hexdigest(),
            }
            if not missing_metadata:
                (output / "run_metadata.json").write_text(json.dumps(evidence), encoding="utf-8")
            (output / "metrics.json").write_text(
                json.dumps({"eval_loss_improvement_pct": 7.141, **evidence}), encoding="utf-8",
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

    def test_failed_download_with_stale_complete_files_is_not_valid(self):
        gate, promoted = self.evaluate(skipped=False, adapter=True,
                                       workflow_status="KAGGLE_OUTPUT_UNAVAILABLE")
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertFalse(promoted)
        self.assertIn("Current GitHub run has no verified COMPLETE Kaggle status", gate["reasons"])

    def test_active_kernel_outputs_cannot_be_claimed(self):
        gate, promoted = self.evaluate(skipped=False, adapter=True,
                                       workflow_status="BLOCKED_EXISTING_KERNEL_ACTIVE")
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertFalse(promoted)

    def test_missing_run_status_fails_closed(self):
        gate, promoted = self.evaluate(skipped=False, adapter=True,
                                       workflow_status="__MISSING__")
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertFalse(promoted)

    def test_complete_run_with_wrong_train_sha_is_rejected(self):
        gate, _ = self.evaluate(False, True, train_sha_override="tampered-train-sha")
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertTrue(any("training_data_sha256" in x for x in gate["reasons"]))

    def test_complete_run_with_wrong_eval_sha_is_rejected(self):
        gate, _ = self.evaluate(False, True, eval_sha_override="tampered-eval-sha")
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertTrue(any("eval_data_sha256" in x for x in gate["reasons"]))

    def test_complete_run_with_wrong_recipe_sha_is_rejected(self):
        gate, _ = self.evaluate(False, True, recipe_sha_override="tampered-recipe-sha")
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertTrue(any("training_recipe_sha256" in x for x in gate["reasons"]))

    def test_complete_run_missing_metadata_is_rejected(self):
        gate, _ = self.evaluate(False, True, missing_metadata=True)
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertTrue(any("run_metadata.json" in x for x in gate["reasons"]))

    def test_real_valid_candidate_requires_independent_review(self):
        gate, promoted = self.evaluate(skipped=False, adapter=True)
        self.assertTrue(gate["automated_precheck_passed"])
        self.assertEqual(gate["human_review_status"], "pending")
        self.assertFalse(gate["promotion_approved"])
        self.assertIn(
            "Independent semantic and safety review pending; automatic promotion disabled.",
            gate["reasons"],
        )
        self.assertFalse(promoted)


if __name__ == "__main__":
    unittest.main()
