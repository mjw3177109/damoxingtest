"""Offline regression tests; never download model or allocate GPU."""
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_tokenizer_contract.py"
spec = importlib.util.spec_from_file_location("tokenizer_contract_audit", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeTokenizer:
    eos_token = "<EOS>"
    eos_token_id = 9999

    def __call__(self, text, add_special_tokens=False):
        ids = []
        i = 0
        while i < len(text):
            if text.startswith(self.eos_token, i):
                ids.append(self.eos_token_id)
                i += len(self.eos_token)
            else:
                ids.append(ord(text[i]) + 1)
                i += 1
        return {"input_ids": ids}


class TokenizerAuditTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = FakeTokenizer()
        self.record = {"instruction": "保护隐私", "response": "先获得同意。"}

    def test_normal_response_eos_supervised(self):
        row = module.audit_records(self.tokenizer, [self.record], 256)[0]
        self.assertTrue(row["eos_at_full_end"])
        self.assertTrue(row["eos_at_supervised_end"])
        self.assertFalse(row["was_truncated"])

    def test_truncation_detected_and_eos_missing(self):
        row = module.audit_records(self.tokenizer, [self.record], 256)[0]
        short = module.audit_records(self.tokenizer, [self.record], row["full_tokens"] - 1)[0]
        self.assertTrue(short["was_truncated"])
        self.assertFalse(short["eos_in_supervised"])
        self.assertFalse(short["eos_at_supervised_end"])
        self.assertGreater(short["supervised_tokens"], 0)

    def test_no_response_supervision_detected(self):
        row = module.audit_records(self.tokenizer, [self.record], 1)[0]
        self.assertTrue(row["zero_supervision"])
        self.assertFalse(row["eos_in_supervised"])

    def test_summary_has_only_aggregates_and_indices(self):
        summary = module.summarize(module.audit_records(self.tokenizer, [self.record], 256))
        self.assertEqual(summary["records"], 1)
        self.assertEqual(summary["eos_not_at_supervised_end"], 0)
        self.assertNotIn("instruction", str(summary))
        self.assertNotIn(self.record["response"], str(summary))


if __name__ == "__main__":
    unittest.main()
