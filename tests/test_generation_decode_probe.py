import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from generation_decode_probe import analyze_tokens, read_prompts


class FakeTokenizer:
    eos_token_id = 0

    def decode(self, ids, skip_special_tokens=True):
        return "".join({0: "", 1: ".", 2: "好", 3: "?"}[value] for value in ids)


class DecodeProbeTests(unittest.TestCase):
    def test_punctuation_and_limit(self):
        result = analyze_tokens([1] * 64, FakeTokenizer(), 64)
        self.assertTrue(result["punctuation_only"])
        self.assertEqual(result["longest_identical_character_run"], 64)
        self.assertEqual(result["stop_reason_inferred"], "max_new_tokens")
        self.assertNotIn("output", result)

    def test_eos_and_opt_in_text(self):
        result = analyze_tokens([2, 0], FakeTokenizer(), 64, include_text=True)
        self.assertEqual(result["stop_reason_inferred"], "eos")
        self.assertEqual(result["eos_position"], 1)
        self.assertEqual(result["output"], "好")

    def test_hash_guard_and_no_prompt_logging(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "eval.jsonl"
            path.write_text(json.dumps({"instruction": "秘密提示", "response": "回答"}, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                read_prompts(path, "wrong", 1)
            prompts, digest = read_prompts(path, "", 1)
            self.assertEqual(len(digest), 64)
            self.assertEqual(prompts[0], "用户：秘密提示\n助手：")


if __name__ == "__main__":
    unittest.main()
