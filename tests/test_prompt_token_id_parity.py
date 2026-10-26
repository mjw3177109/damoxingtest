"""Offline negative and positive tests; no tokenizer downloads or GPU."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools/audit_prompt_token_id_parity.py"
spec = importlib.util.spec_from_file_location("prompt_parity", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeTokenizer:
    def __init__(self, extra=False):
        self.extra = extra

    def __call__(self, text, add_special_tokens=True):
        ids = [ord(c) for c in text]
        if self.extra and add_special_tokens:
            ids = [999999] + ids
        return {"input_ids": ids}


class PromptTokenParityTests(unittest.TestCase):
    def setUp(self):
        self.prompts = [f"用户：问题{i}\\n助手：" for i in range(10)]

    def test_same_ids_are_reported_as_no_change(self):
        r = module.compare_token_ids(FakeTokenizer(), self.prompts)
        self.assertEqual((r["prompt_count"], r["different_token_id_sequences"], r["length_differences"]), (10, 0, 0))

    def test_extra_default_bos_is_detected(self):
        r = module.compare_token_ids(FakeTokenizer(extra=True), self.prompts)
        self.assertEqual((r["different_token_id_sequences"], r["length_differences"]), (10, 10))

    def test_rejects_partial_holdout(self):
        with self.assertRaisesRegex(ValueError, "ten"):
            module.compare_token_ids(FakeTokenizer(), self.prompts[:9])

    def test_rejects_wrong_holdout_sha(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "holdout.jsonl"
            path.write_text('{"instruction":"x","response":"y"}\\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                module.load_prompts(path)

    def test_output_excludes_raw_prompt_and_token_ids(self):
        r = module.compare_token_ids(FakeTokenizer(), self.prompts)
        self.assertNotIn("问题0", str(r))
        self.assertNotIn("input_ids", str(r))


if __name__ == "__main__":
    unittest.main()
