"""No-model regression tests for Run 12 EOS label audit."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_run12_eos_labels import audit_rows


class FakeTokenizer:
    eos_token = "<EOS>"
    eos_token_id = 99

    def __call__(self, text, add_special_tokens=True):
        if add_special_tokens:
            raise AssertionError("Must match training: no automatic special tokens")
        return {"input_ids": [3] * len(text.replace(self.eos_token, "")) +
                ([self.eos_token_id] if text.endswith(self.eos_token) else [])}


class EosLabelTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"instruction": "你好", "response": "保护用户"}]
        self.tok = FakeTokenizer()

    def test_terminal_eos_supervised(self):
        result = audit_rows(self.rows, self.tok, 256)
        self.assertEqual(result["terminal_eos_supervised_count"], 1)
        self.assertEqual(result["records_truncated_count"], 0)
        self.assertEqual(result["answer_terminal_eos_missing_count"], 0)
        self.assertEqual(result["records_without_supervised_tokens"], 0)

    def test_truncation_loses_terminal_eos(self):
        result = audit_rows(self.rows, self.tok, 11)
        self.assertEqual(result["terminal_eos_supervised_count"], 0)
        self.assertEqual(result["records_truncated_count"], 1)

    def test_no_supervision_detected(self):
        result = audit_rows(self.rows, self.tok, 2)
        self.assertEqual(result["records_without_supervised_tokens"], 1)

    def test_missing_eos_detected(self):
        class Broken(FakeTokenizer):
            def __call__(self, text, add_special_tokens=True):
                return {"input_ids": [3] * len(text)}
        result = audit_rows(self.rows, Broken(), 256)
        self.assertEqual(result["answer_terminal_eos_missing_count"], 1)
        self.assertEqual(result["terminal_eos_supervised_count"], 0)

    def test_bad_length_rejected(self):
        with self.assertRaises(ValueError):
            audit_rows(self.rows, self.tok, 1)


if __name__ == "__main__":
    unittest.main()
