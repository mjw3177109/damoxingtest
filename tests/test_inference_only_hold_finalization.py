"""CPU-only regression: intentional inference-only hold must be reported truthfully.

No Kaggle access, model weights, GPU, or credentials are needed.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InferenceOnlyHoldFinalizationTests(unittest.TestCase):
    def test_hold_finalization_is_not_training_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-test"
            output = run_dir / "kaggle_output" / "training_output"
            output.mkdir(parents=True)
            (run_dir / "status.txt").write_text(
                "BLOCKED_INFERENCE_ONLY_CHANGE\n", encoding="utf-8"
            )
            (output / "training_status.json").write_text(
                json.dumps({
                    "status": "blocked",
                    "reason": "audited_inference_only_change",
                    "kaggle_kernel_submitted": False,
                    "current_run_performed_gpu_training": False,
                }),
                encoding="utf-8",
            )
            (output / "training.log").write_text(
                "BLOCKED_INFERENCE_ONLY_CHANGE; no Kaggle submission.\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "finalize_report.py"),
                 "--run-dir", str(run_dir)],
                cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (run_dir / "final_status.txt").read_text(encoding="utf-8").strip(),
                "BLOCKED_INFERENCE_ONLY_CHANGE",
            )
            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("未提交 Kaggle、未执行 GPU 训练或新评估", report)
            self.assertIn("主动防止重复 GPU 提交的预期安全阻断", report)
            self.assertIn("CPU 推理对照", report)
            self.assertNotIn("最终判定： **SUCCESS**", report)
            self.assertFalse((run_dir / "metrics.json").exists())
            self.assertFalse((run_dir / "samples.json").exists())


if __name__ == "__main__":
    unittest.main()
