"""Offline punctuation audit regressions; no private data, model, or GPU."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.punctuation_collapse_audit import audit, is_punctuation_only, max_punctuation_run, summarize


class PunctuationCollapseAuditTests(unittest.TestCase):
    def test_punctuation_only_uses_unicode_categories(self):
        self.assertTrue(is_punctuation_only("......？？"))
        self.assertTrue(is_punctuation_only("  ！。 "))
        self.assertFalse(is_punctuation_only("请先确认。"))
        self.assertFalse(is_punctuation_only("   "))

    def test_repetition_run_and_ratio(self):
        result = summarize(["请确认。", "........", "????", "答复：正常。"])
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["punctuation_only"], 2)
        self.assertEqual(result["eight_plus_identical_punctuation_run"], 1)
        self.assertEqual(result["max_identical_punctuation_run"], 8)
        self.assertEqual(result["starts_punctuation"], 2)
        self.assertEqual(max_punctuation_run("句子。。。句子"), 3)

    def test_audit_does_not_expose_raw_examples(self):
        secret = "private-example-marker-DO-NOT-EMIT"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            train = root / "train.jsonl"
            holdout = root / "eval.jsonl"
            samples = root / "samples.json"
            train.write_text(json.dumps({"instruction": secret, "response": "正常回答。"}, ensure_ascii=False) + "\n", encoding="utf-8")
            holdout.write_text(json.dumps({"instruction": "x", "response": "回答正常。"}, ensure_ascii=False) + "\n", encoding="utf-8")
            samples.write_text(json.dumps([{"prompt": secret, "output": "........"}]), encoding="utf-8")
            result = audit(train, holdout, samples)
            self.assertEqual(result["train_responses"]["count"], 1)
            self.assertEqual(result["historical_samples"]["punctuation_only"], 1)
            self.assertNotIn(secret, json.dumps(result))
            self.assertNotIn("正常回答", json.dumps(result, ensure_ascii=False))

    def test_reject_malformed_sample_without_echoing_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "train").write_text('{"response":"正常"}\n', encoding="utf-8")
            (root / "eval").write_text('{"response":"正常"}\n', encoding="utf-8")
            (root / "samples").write_text('{"prompt":"secret","output":42}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "samples.json must be a list"):
                audit(root / "train", root / "eval", root / "samples")


if __name__ == "__main__":
    unittest.main()
