"""Regression tests: skipped Kaggle runs must not appear to retrain or re-evaluate."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "finalize_report.py"


class FinalizeSkippedRunTests(unittest.TestCase):
    def run_report(self, skipped):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            output = run / "kaggle_output" / "training_output"
            stages = output / "stages"
            stages.mkdir(parents=True)
            (stages / "stage3_lora_training.md").write_text(
                "Adapter saved in this run", encoding="utf-8"
            )
            (run / "status.txt").write_text("COMPLETE\n", encoding="utf-8")
            (output / "training_status.json").write_text(
                json.dumps({
                    "status": "completed",
                    "skipped_no_changes": skipped,
                    "reused_from_run": "reports/2026-10-23/run-39921870784",
                }), encoding="utf-8"
            )
            (output / "metrics.json").write_text(
                json.dumps({
                    "model_name": "test-model", "train_examples": 85,
                    "validation_examples": 24, "base_eval_loss": 3.4,
                    "final_eval_loss": 3.1, "eval_loss_improvement_pct": 8.8,
                    "train_runtime_seconds": 67, "gpu_name": None,
                    "gpu_memory_gib": None,
                }), encoding="utf-8"
            )
            (output / "run_metadata.json").write_text(
                json.dumps({"source_run_gpu_name": "Tesla T4",
                            "source_run_gpu_memory_gib": 14.56}), encoding="utf-8"
            )
            (output / "samples.json").write_text(
                json.dumps([{"prompt": "test", "output": "...."}]), encoding="utf-8"
            )
            (output / "training.log").write_text(
                "No data or training-recipe changes detected.\n", encoding="utf-8"
            )
            env = dict(os.environ, GITHUB_RUN_ID="40065584092",
                       GITHUB_REPOSITORY="mjw3177109/damoxingtest")
            subprocess.run(
                [sys.executable, str(SCRIPT), "--run-dir", str(run)],
                check=True, env=env, capture_output=True, text=True,
            )
            report = (run / "report.md").read_text(encoding="utf-8")
            status = (run / "final_status.txt").read_text(encoding="utf-8").strip()
            stage_exists = (run / "stages" / "stage3_lora_training.md").exists()
            return report, status, stage_exists

    def test_skipped_run_marks_historical_metrics_and_no_new_training(self):
        report, status, stage_exists = self.run_report(skipped=True)
        self.assertEqual(status, "SKIPPED_NO_CHANGES")
        self.assertIn("历史复用指标（本轮未训练或重新评估）", report)
        self.assertIn("本次未进行新的训练或评估", report)
        self.assertIn("历史来源：Tesla T4", report)
        self.assertIn("历史训练耗时", report)
        self.assertIn("历史复用生成样例", report)
        self.assertNotIn("本次验证集 loss 在", report)
        self.assertFalse(stage_exists)
        self.assertIn("本次未执行训练阶段", report)

    def test_real_completed_run_retains_stage_and_current_metrics(self):
        report, status, stage_exists = self.run_report(skipped=False)
        self.assertEqual(status, "SUCCESS")
        self.assertIn("## 本次结果", report)
        self.assertIn("本次验证集 loss 在", report)
        self.assertTrue(stage_exists)
        self.assertNotIn("历史复用指标", report)


if __name__ == "__main__":
    unittest.main()
