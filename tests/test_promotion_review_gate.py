"""Offline regression: automatic checks must never publish an unreviewed adapter.

Executes the actual quality-gate Python heredoc with synthetic fixtures.
No Kaggle credentials, network, model download, GPU or real user data.
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


def gate_script():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    section = workflow.split("      - name: Candidate quality gate and approved-adapter promotion\n", 1)[1]
    section = section.split("      - name: Upload model weights and full outputs\n", 1)[0]
    lines = section.splitlines()
    start = next(i for i, line in enumerate(lines) if "python - <<'PY'" in line)
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "PY")
    return textwrap.dedent("\n".join(lines[start + 1:end]))


class PromotionReviewGateTests(unittest.TestCase):
    def run_gate(self, *, skipped=False, valid_samples=True):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "reports" / "synthetic"
            output = run_dir / "kaggle_output"
            output.mkdir(parents=True)
            (output / "training_status.json").write_text(
                json.dumps({"status": "completed", "skipped_no_changes": skipped}),
                encoding="utf-8",
            )
            (output / "metrics.json").write_text(
                json.dumps({"eval_loss_improvement_pct": 7.0}),
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
            env.update({"RUN_DIR": str(run_dir), "GITHUB_RUN_ID": "123456"})
            result = subprocess.run(
                [sys.executable, "-c", gate_script()],
                cwd=root, env=env, capture_output=True, text=True, timeout=10,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            gate = json.loads((run_dir / "quality_gate.json").read_text(encoding="utf-8"))
            self.assertFalse((root / "checkpoints" / "adapter_latest").exists())
            self.assertFalse((root / "checkpoints" / "adapter_version.json").exists())
            return gate

    def test_valid_heuristic_still_requires_review(self):
        gate = self.run_gate()
        self.assertTrue(gate["automated_precheck_passed"])
        self.assertEqual(gate["human_review_status"], "pending")
        self.assertFalse(gate["promotion_approved"])
        self.assertTrue(any("review" in reason.lower() for reason in gate["reasons"]))

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
