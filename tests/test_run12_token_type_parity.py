"""Offline contract tests for Run 12 token_type_ids parity audit."""
import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("token_type_parity", TOOLS / "run12_token_type_parity.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeTensor:
    shape = (1, 3)


class FakeTokenizer:
    def __call__(self, text, return_tensors=None):
        return {"input_ids": FakeTensor(), "attention_mask": FakeTensor(),
                "token_type_ids": FakeTensor()}


class TokenTypeParityTests(unittest.TestCase):
    def test_original_preserves_token_type_ids(self):
        self.assertIn("token_type_ids", module.make_inputs(FakeTokenizer(), "hello", "original"))

    def test_training_parity_removes_only_token_type_ids(self):
        result = module.make_inputs(FakeTokenizer(), "hello", "train_parity")
        self.assertEqual(set(result), {"input_ids", "attention_mask"})

    def test_unknown_setting_rejected(self):
        with self.assertRaises(ValueError):
            module.make_inputs(FakeTokenizer(), "hello", "not_real")

    def test_missing_token_type_ids_rejected(self):
        class NoTypes(FakeTokenizer):
            def __call__(self, text, return_tensors=None):
                result = super().__call__(text, return_tensors)
                result.pop("token_type_ids")
                return result
        with self.assertRaisesRegex(ValueError, "token_type_ids"):
            module.make_inputs(NoTypes(), "hello", "train_parity")

    def test_summary_requires_exactly_40_paired_results(self):
        with self.assertRaises(ValueError):
            module.summarize([])

    def test_historical_control_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Base control"):
            module.verify_historical_control({"base/original": {"punctuation_only": 0},
                                              "candidate/original": {"punctuation_only": 10}})


if __name__ == "__main__":
    unittest.main()
