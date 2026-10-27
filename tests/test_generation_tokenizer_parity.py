"""Offline AST regression for GPT-2 training/generation tokenizer parity.

No model download, GPU, Kaggle credentials, or inference is required.
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "train_gpt2_lora.py"


def calls_for_argument(tree, argument):
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "tokenizer"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == argument
    ]


def disables_special_tokens(call):
    return any(
        keyword.arg == "add_special_tokens"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is False
        for keyword in call.keywords
    )


class GenerationTokenizerParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_text(encoding="utf-8"))

    def test_training_prefix_and_answer_are_explicit(self):
        for argument in ("prefix", "answer"):
            with self.subTest(argument=argument):
                calls = calls_for_argument(self.tree, argument)
                self.assertEqual(len(calls), 1)
                self.assertTrue(disables_special_tokens(calls[0]))

    def test_generation_prompt_matches_training_encoding(self):
        calls = calls_for_argument(self.tree, "prompt")
        self.assertEqual(len(calls), 1)
        self.assertTrue(disables_special_tokens(calls[0]))

    def test_response_only_collator_remains_wired(self):
        trainers = [
            node for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Trainer"
        ]
        self.assertEqual(len(trainers), 1)
        collators = [
            keyword.value for keyword in trainers[0].keywords
            if keyword.arg == "data_collator"
        ]
        self.assertEqual(len(collators), 1)
        self.assertIsInstance(collators[0], ast.Name)
        self.assertEqual(collators[0].id, "response_only_collator")


if __name__ == "__main__":
    unittest.main()
