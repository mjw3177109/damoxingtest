"""Offline regression: automatic checks must never publish an unreviewed adapter.

Executes the actual quality-gate Python heredoc with synthetic fixtures.
No Kaggle credentials, network, model download, GPU or real user data.
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
GIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def gate_script():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    section = workflow.split("      - name: Candidate quality gate and approved-adapter promotion\n", 1)[1]
    section = section.split("      - name: Upload model weights and full outputs\n", 1)[0]
    lines = section.splitlines()
    start = next(i for i, line in enumerate(lines) if "python - <<'PY'" in line)
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "PY")
    return textwrap.dedent("\n".join(lines[start + 1:end]))


class PromotionReviewGateTests(unittest.TestCase):
    def run_gate(self, *, skipped=False, valid_samples=True, existing_approved=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "reports" / "synthetic"
            output = run_dir / "kaggle_output"
            output.mkdir(parents=True)
            (run_dir / "status.txt").write_text(
                "PRE_SUBMIT_SKIPPED_NO_CHANGES\n" if skipped else "COMPLETE\n", encoding="utf-8"
            )
            # Protect an existing approved checkpoint during every gate outcome.
            approved_dir = root / "checkpoints" / "adapter_latest"
            approved_version = root / "checkpoints" / "adapter_version.json"
            if existing_approved:
                approved_dir.mkdir(parents=True)
                (approved_dir / "adapter_model.safetensors").write_bytes(b"approved-model-v1")
                approved_version.write_text('{"version":"approved-v1"}', encoding="utf-8")
            (output / "training_status.json").write_text(
                json.dumps({"status": "completed", "skipped_no_changes": skipped}),
                encoding="utf-8",
            )
            # A valid candidate must carry matching local data and recipe evidence.
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
                source = root / relative
                source.write_text("fixture", encoding="utf-8")
                recipe.update(relative.encode("utf-8"))
                recipe.update(source.read_bytes())
            evidence = {
                "training_data_sha256": hashlib.sha256(train.read_bytes()).hexdigest(),
                "eval_data_sha256": hashlib.sha256(holdout.read_bytes()).hexdigest(),
                "training_recipe_sha256": recipe.hexdigest(),
                "source_git_commit_sha": GIT_SHA,
            }
            (output / "run_metadata.json").write_text(json.dumps(evidence), encoding="utf-8")
            (output / "metrics.json").write_text(
                json.dumps({"eval_loss_improvement_pct": 7.0, **evidence}),
                encoding="utf-8",
            )
            answer = "这是完整的中文回答，包含具体行动步骤并提醒核实证据。" if valid_samples else "........"
            (output / "samples.json").write_text(
                json.dumps([{"output": answer} for _ in range(10)], ensure_ascii=False),
                encoding="utf-8",
            )
            adapter = output / "adapter"
            adapter.mkdir()
            (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
            env = os.environ.copy()
            env.update({"RUN_DIR": str(run_dir), "GITHUB_RUN_ID": "123456",
                        "GITHUB_SHA": GIT_SHA})
            result = subprocess.run(
                [sys.executable, "-c", gate_script()],
                cwd=root, env=env, capture_output=True, text=True, timeout=10,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            gate = json.loads((run_dir / "quality_gate.json").read_text(encoding="utf-8"))
            if existing_approved:
                self.assertEqual(
                    (approved_dir / "adapter_model.safetensors").read_bytes(),
                    b"approved-model-v1",
                )
                self.assertEqual(
                    approved_version.read_text(encoding="utf-8"),
                    '{"version":"approved-v1"}',
                )
            else:
                self.assertFalse(approved_dir.exists())
                self.assertFalse(approved_version.exists())
            return gate

    def test_valid_heuristic_still_requires_review(self):
        gate = self.run_gate()
        self.assertTrue(gate["automated_precheck_passed"])
        self.assertEqual(gate["human_review_status"], "pending")
        self.assertFalse(gate["promotion_approved"])
        self.assertTrue(any("review" in reason.lower() for reason in gate["reasons"]))

    def test_existing_approved_checkpoint_survives_good_precheck(self):
        gate = self.run_gate(existing_approved=True)
        self.assertTrue(gate["automated_precheck_passed"])
        self.assertFalse(gate["promotion_approved"])

    def test_existing_approved_checkpoint_survives_bad_generation(self):
        gate = self.run_gate(existing_approved=True, valid_samples=False)
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertFalse(gate["promotion_approved"])

    def test_bad_generation_never_promotes(self):
        gate = self.run_gate(valid_samples=False)
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertFalse(gate["promotion_approved"])

    def test_reused_training_never_promotes(self):
        gate = self.run_gate(skipped=True)
        self.assertFalse(gate["automated_precheck_passed"])
        self.assertTrue(gate["evidence_reused"])
        self.assertFalse(gate["promotion_approved"])


if __name__ == "__main__":
    unittest.main()
