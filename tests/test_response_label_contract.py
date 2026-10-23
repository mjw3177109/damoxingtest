"""CPU-free behavioral regression tests for the training response-only contract.

The real nested functions are extracted from the training source via AST. No
model, network, CUDA, Kaggle credential, or third-party dependency is needed.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "train_gpt2_lora.py"


class FakeTokenizer:
    eos_token = "<EOS>"
    eos_token_id = 999999
    pad_token_id = 0

    def __call__(self, text, add_special_tokens=False):
        ids = []
        index = 0
        while index < len(text):
            if text.startswith(self.eos_token, index):
                ids.append(self.eos_token_id)
                index += len(self.eos_token)
            else:
                ids.append(ord(text[index]) + 1)
                index += 1
        return {"input_ids": ids}


class FakeTensor:
    def __init__(self, data):
        self.data = data

    def __setitem__(self, index, value):
        row, column = index
        self.data[row][column] = value.data


class FakeTorch:
    long = "long"

    @staticmethod
    def full(shape, fill_value, dtype=None):
        rows, cols = shape
        return FakeTensor([[fill_value] * cols for _ in range(rows)])

    @staticmethod
    def zeros(shape, dtype=None):
        return FakeTorch.full(shape, 0, dtype=dtype)

    @staticmethod
    def tensor(values, dtype=None):
        return FakeTensor(list(values))


def load_training_function(name, context):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(nodes) != 1:
        raise AssertionError(f"Expected one {name}, found {len(nodes)}")
    module = ast.fix_missing_locations(ast.Module(body=[nodes[0]], type_ignores=[]))
    scope = dict(context)
    exec(compile(module, str(SOURCE), "exec"), scope)
    return scope[name]


class ResponseOnlyContractTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = FakeTokenizer()
        self.args = SimpleNamespace(max_length=256)
        self.encode = load_training_function("encode_record", {"tokenizer": self.tokenizer, "args": self.args})
        self.collate = load_training_function("response_only_collator", {"tokenizer": self.tokenizer, "torch": FakeTorch})

    def test_prefix_is_masked_and_answer_eos_is_supervised(self):
        record = {"instruction": "保护隐私", "response": "先取得授权。"}
        item = self.encode(record)
        prefix = self.tokenizer("用户：保护隐私\n助手：")["input_ids"]
        answer = self.tokenizer("先取得授权。<EOS>")["input_ids"]
        self.assertEqual(item["input_ids"], prefix + answer)
        self.assertEqual(item["labels"], [-100] * len(prefix) + answer)
        self.assertEqual(item["labels"][-1], self.tokenizer.eos_token_id)
        self.assertEqual(item["attention_mask"], [1] * len(item["input_ids"]))

    def test_exact_length_boundary_retains_eos(self):
        record = {"instruction": "甲", "response": "乙"}
        full = self.encode(record)
        self.args.max_length = len(full["input_ids"])
        item = self.encode(record)
        self.assertEqual(item["labels"][-1], self.tokenizer.eos_token_id)

    def test_truncated_prefix_is_rejected(self):
        self.args.max_length = 4
        with self.assertRaisesRegex(ValueError, "no response tokens"):
            self.encode({"instruction": "很长的指令", "response": "回答"})

    def test_batch_padding_never_contributes_to_loss(self):
        first = self.encode({"instruction": "短", "response": "好"})
        second = self.encode({"instruction": "更长的提问", "response": "需要说明"})
        batch = self.collate([first, second])
        for index, item in enumerate((first, second)):
            length = len(item["input_ids"])
            self.assertEqual(batch["input_ids"].data[index][:length], item["input_ids"])
            self.assertEqual(batch["labels"].data[index][:length], item["labels"])
            self.assertEqual(batch["labels"].data[index][length:], [-100] * (len(second["input_ids"]) - length))
            self.assertEqual(batch["attention_mask"].data[index][length:], [0] * (len(second["input_ids"]) - length))

    def test_trainer_wires_response_only_collator(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        trainers = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Trainer"]
        self.assertEqual(len(trainers), 1)
        wired = [kw.value for kw in trainers[0].keywords if kw.arg == "data_collator"]
        self.assertEqual(len(wired), 1)
        self.assertIsInstance(wired[0], ast.Name)
        self.assertEqual(wired[0].id, "response_only_collator")
        self.assertNotIn("DataCollatorForLanguageModeling", SOURCE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
