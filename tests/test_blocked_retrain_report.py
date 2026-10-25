"""Offline regression tests for honest blocked-retrain report finalization."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import finalize_report


class BlockedRetrainReportTests(unittest.TestCase):
    def test_blocked_same_data_report_explains_approval_without_gpu_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "reports" / "2026-10-26" / "run-guard-test"
            run_dir.mkdir(parents=True)
            (run_dir / "status.txt").write_text(
                "BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL\n", encoding="utf-8"
            )
            with patch.object(sys, "argv", [
                "finalize_report.py", "--run-dir", str(run_dir)
            ]):
                finalize_report.main()
            self.assertEqual(
                (run_dir / "final_status.txt").read_text(encoding="utf-8").strip(),
                "BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL",
            )
            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("未提交 Kaggle Kernel", report)
            self.assertIn("未执行 GPU 训练或评估", report)
            self.assertIn("workflow_dispatch", report)
            self.assertIn("approve_same_data_retrain", report)
            self.assertIn("GPU 配额", report)
            self.assertIn("没有找到有效的 metrics.json", report)
            self.assertIn("不能将其误判为凭据", report)
            self.assertNotIn("请先解决凭据、GPU", report)
            self.assertFalse((run_dir / "metrics.json").exists())
            self.assertFalse((run_dir / "samples.json").exists())

    def test_failed_kernel_requires_review_not_automatic_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "reports" / "2026-10-26" / "run-failed-kernel"
            run_dir.mkdir(parents=True)
            (run_dir / "status.txt").write_text(
                "BLOCKED_FAILED_KERNEL_REQUIRES_APPROVAL\n", encoding="utf-8"
            )
            with patch.object(sys, "argv", [
                "finalize_report.py", "--run-dir", str(run_dir)
            ]):
                finalize_report.main()
            self.assertEqual(
                (run_dir / "final_status.txt").read_text(encoding="utf-8").strip(),
                "BLOCKED_FAILED_KERNEL_REQUIRES_APPROVAL",
            )
            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("未提交新的 Kaggle Kernel", report)
            self.assertIn("未执行新的 GPU 训练或评估", report)
            self.assertIn("approve_failed_kernel_retry", report)
            self.assertIn("先核实远端失败 Kernel 的实际日志", report)
            self.assertNotIn("请先解决凭据、GPU", report)
            self.assertFalse((run_dir / "metrics.json").exists())


if __name__ == "__main__":
    unittest.main()
