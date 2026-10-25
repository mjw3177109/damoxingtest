"""Offline regression tests for near-duplicate screening (no model/GPU/network)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_holdout_near_duplicates.py"
spec = importlib.util.spec_from_file_location("holdout_near_duplicates", SOURCE)
audit_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_tool)


class HoldoutNearDuplicateTests(unittest.TestCase):
    def test_near_duplicate_detected(self):
        train = [(85, {"instruction": "模型输出事实错误，但训练损失下降，应该怎么办？", "response": "记录错误样例，检查训练数据是否提供正确监督，并用独立事实性测试评估修复；不能以 loss 改善掩盖事实错误。"})]
        evals = [(19, {"instruction": "模型输出的事实错误，但训练损失有所下降，应该怎么办？", "response": "记录错误类型与样例，检查训练数据是否提供正确监督，并用独立事实性测试评估修复；不能以 loss 改善掩盖事实错误。"})]
        result = audit_tool.audit(train, evals)
        self.assertEqual(len(result["near_duplicate_pairs"]), 1)
        self.assertEqual((result["near_duplicate_pairs"][0]["train_line"], result["near_duplicate_pairs"][0]["eval_line"]), (85, 19))

    def test_unrelated_pairs_not_flagged(self):
        train = [(1, {"instruction": "怎样安全保护用户隐私", "response": "尊重授权并保护用户资料"})]
        evals = [(1, {"instruction": "今天的天气如何", "response": "请查询最新气象预报"})]
        self.assertEqual(audit_tool.audit(train, evals)["near_duplicate_pairs"], [])

    def test_normalization_handles_spacing_punctuation(self):
        self.assertEqual(audit_tool.normalized(" A，Ｂ  中 文。"), "ab中文")

    def test_no_raw_text_in_output(self):
        train = [(1, {"instruction": "测试秘密示例", "response": "不能暴露示例隐私"})]
        result = audit_tool.audit(train, train)
        self.assertNotIn("秘密", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("隐私", json.dumps(result, ensure_ascii=False))

    def test_strict_mode_is_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = Path(tmp) / "train.jsonl"
            evals = Path(tmp) / "eval.jsonl"
            row = json.dumps({"instruction": "不应泄露任何个人信息", "response": "请尊重隐私并核实授权"}, ensure_ascii=False) + "\n"
            train.write_text(row, encoding="utf-8")
            evals.write_text(row, encoding="utf-8")
            from contextlib import redirect_stdout
            from io import StringIO
            with redirect_stdout(StringIO()):
                self.assertEqual(audit_tool.main(["--train", str(train), "--eval", str(evals)]), 0)
                self.assertEqual(audit_tool.main(["--train", str(train), "--eval", str(evals), "--strict"]), 2)


if __name__ == "__main__":
    unittest.main()
