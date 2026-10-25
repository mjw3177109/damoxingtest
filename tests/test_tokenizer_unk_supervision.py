"""Offline UNK-supervision audit tests; no model downloads or GPU."""
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_tokenizer_contract.py"
spec = importlib.util.spec_from_file_location("unk_audit", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeTokenizer:
    eos_token = "<EOS>"
    eos_token_id = 999
    unk_token_id = 777

    def __call__(self, text, add_special_tokens=False):
        ids = []
        i = 0
        while i < len(text):
            if text.startswith(self.eos_token, i):
                ids.append(self.eos_token_id)
                i += len(self.eos_token)
            else:
                ids.append(self.unk_token_id if text[i] == "!" else ord(text[i]) + 1000)
                i += 1
        return {"input_ids": ids}


class NoUnkTokenizer:
    eos_token = "<EOS>"
    eos_token_id = 999

    def __call__(self, text, add_special_tokens=False):
        return FakeTokenizer()(text, add_special_tokens=add_special_tokens)


class UnkSupervisionTests(unittest.TestCase):
    def setUp(self):
        self.record = {"instruction": "隐私!", "response": "答!"}

    def test_prefix_and_answer_unk_counts_are_separate(self):
        row = audit.audit_records(FakeTokenizer(), [self.record], 256)[0]
        self.assertEqual(row["prefix_unk_tokens"], 1)
        self.assertEqual(row["answer_unk_tokens"], 1)
        self.assertEqual(row["supervised_unk_tokens"], 1)
        self.assertTrue(row["eos_at_supervised_end"])

    def test_aggregate_counts_and_denominators(self):
        rows = audit.audit_records(FakeTokenizer(), [self.record, self.record], 256)
        summary = audit.summarize(rows)
        self.assertEqual(summary["unk_prefix"]["count"], 2)
        self.assertEqual(summary["unk_answer"]["count"], 2)
        self.assertEqual(summary["unk_supervised"]["count"], 2)
        self.assertEqual(summary["unk_answer"]["total_tokens"], sum(r["answer_tokens"] for r in rows))
        self.assertGreater(summary["unk_supervised"]["percent"], 0)
        self.assertNotIn(self.record["response"], str(summary))

    def test_truncated_answer_counts_only_supervised_tokens(self):
        full = audit.audit_records(FakeTokenizer(), [self.record], 256)[0]
        max_length = full["prefix_tokens"] + 1
        row = audit.audit_records(FakeTokenizer(), [self.record], max_length)[0]
        self.assertEqual(row["answer_unk_tokens"], 1)
        self.assertEqual(row["supervised_unk_tokens"], 0)
        self.assertFalse(row["eos_in_supervised"])

    def test_unknown_unk_id_is_not_reported_as_zero(self):
        row = audit.audit_records(NoUnkTokenizer(), [self.record], 256)[0]
        self.assertIsNone(row["prefix_unk_tokens"])
        summary = audit.summarize([row])
        self.assertIsNone(summary["unk_supervised"]["count"])
        self.assertIsNone(summary["unk_supervised"]["percent"])


if __name__ == "__main__":
    unittest.main()
