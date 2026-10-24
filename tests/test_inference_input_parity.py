"""Offline regression for GPT-2 inference input-field parity; no model/GPU/network."""
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "train_gpt2_lora.py"
spec = importlib.util.spec_from_file_location("gpt2_training_parity", SOURCE)
training = importlib.util.module_from_spec(spec)
spec.loader.exec_module(training)


class FakeEncoding(dict):
    def to(self, device):
        self.device = device
        return self


class FakeTokenizer:
    def __init__(self, with_types=True):
        self.with_types = with_types
        self.calls = []

    def __call__(self, text, return_tensors=None):
        self.calls.append((text, return_tensors))
        fields = {"input_ids": [1, 2], "attention_mask": [1, 1]}
        if self.with_types:
            fields["token_type_ids"] = [0, 0]
        return FakeEncoding(fields)


class InferenceInputParityTests(unittest.TestCase):
    def test_removes_only_token_type_ids(self):
        tokenizer = FakeTokenizer()
        result = training.prepare_generation_inputs(tokenizer, "用户：测试\n助手：", "cpu")
        self.assertEqual(set(result), {"input_ids", "attention_mask"})
        self.assertEqual(result["input_ids"], [1, 2])
        self.assertEqual(result["attention_mask"], [1, 1])
        self.assertEqual(result.device, "cpu")
        self.assertEqual(tokenizer.calls, [("用户：测试\n助手：", "pt")])

    def test_missing_token_type_ids_is_supported(self):
        result = training.prepare_generation_inputs(FakeTokenizer(with_types=False), "prompt", "cpu")
        self.assertEqual(set(result), {"input_ids", "attention_mask"})

    def test_other_fields_preserved(self):
        class ExtraTokenizer(FakeTokenizer):
            def __call__(self, text, return_tensors=None):
                encoded = super().__call__(text, return_tensors=return_tensors)
                encoded["position_ids"] = [0, 1]
                return encoded
        result = training.prepare_generation_inputs(ExtraTokenizer(), "prompt", "cpu")
        self.assertEqual(result["position_ids"], [0, 1])
        self.assertNotIn("token_type_ids", result)

    def test_training_generate_path_uses_helper(self):
        import ast
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "prepare_generation_inputs"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0].args), 3)


if __name__ == "__main__":
    unittest.main()
