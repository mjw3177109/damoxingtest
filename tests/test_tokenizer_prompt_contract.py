"""Offline contract checks for consistent training/inference prompt tokenization.

These tests parse source; no model downloads, GPU or user data required.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN = "scripts/train_gpt2_lora.py"
INFERENCE = (
    TRAIN,
    "tools/generation_decode_probe.py",
    "tools/run12_temperature_pair_cpu.py",
)


def tokenizer_calls(relative_path, variable):
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "tokenizer"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == variable
    ]


def disables_automatic_special_tokens(call):
    return any(
        kw.arg == "add_special_tokens"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is False
        for kw in call.keywords
    )


class TokenizerPromptContractTests(unittest.TestCase):
    def test_training_prefix_and_answer_disable_automatic_special_tokens(self):
        for variable in ("prefix", "answer"):
            calls = tokenizer_calls(TRAIN, variable)
            self.assertEqual(len(calls), 1, variable)
            self.assertTrue(disables_automatic_special_tokens(calls[0]), variable)

    def test_all_generation_entrypoints_match_training_tokenization(self):
        for path in INFERENCE:
            with self.subTest(path=path):
                calls = tokenizer_calls(path, "prompt")
                self.assertEqual(len(calls), 1)
                self.assertTrue(disables_automatic_special_tokens(calls[0]))

    def test_training_and_cpu_probes_use_identical_chat_prefixes(self):
        training = (ROOT / TRAIN).read_text(encoding="utf-8")
        probe = (ROOT / "tools/generation_decode_probe.py").read_text(encoding="utf-8")
        paired = (ROOT / "tools/run12_temperature_pair_cpu.py").read_text(encoding="utf-8")
        self.assertIn('prefix = "用户：" + record["instruction"] + "\\n助手："', training)
        self.assertIn('prompts = ["用户：" + item["instruction"] + "\\n助手："', training)
        self.assertIn('prompts.append("用户：" + row["instruction"] + "\\n助手：")', probe)
        self.assertIn("read_prompts(", paired)


if __name__ == "__main__":
    unittest.main()
