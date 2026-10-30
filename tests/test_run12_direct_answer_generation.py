"""Dependency-free regression tests for bounded Run 12 CPU generation evidence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_direct_answer_generation import build_row, summarize


class FakeTokenizer:
    all_special_ids = [0, 1]
    unk_token_id = 1
    eos_token_id = 0
    pad_token_id = 0

    def decode(self, ids, skip_special_tokens=True):
        return "".join("" if skip_special_tokens and t in (0, 1)
                       else "[UNK]" if t == 1 else "[EOS]" if t == 0 else "好" if t == 2 else "."
                       for t in ids)


def rows():
    return [{"phase": p, "setting": s, "prompt_index": i,
             "punctuation_only": p == "candidate" and s == "control" and i < 2,
             "blank_output": False, "contains_chinese": True,
             "stop_reason_inferred": "eos", "unk_token_count": 0,
             "generated_token_count": 1, "longest_identical_character_run": 1}
            for p in ("base", "candidate") for s in ("control", "direct_answer") for i in range(4)]


class DirectAnswerGenerationTests(unittest.TestCase):
    def test_exact_16_paired_generations(self):
        summary = summarize(rows())
        self.assertEqual(summary["candidate/control"]["punctuation_only"], 2)
        self.assertTrue(summary["control_matches_previous_cpu_review"])

    def test_rejects_duplicate_or_missing_pair(self):
        for altered in (rows()[:-1], rows()[:-1] + [rows()[0]]):
            with self.assertRaises(ValueError):
                summarize(altered)

    def test_unknown_only_blank_is_not_good_answer(self):
        row = build_row("candidate", "direct_answer", 0, "用户：测试\n助手：", [1] * 64, FakeTokenizer())
        self.assertTrue(row["blank_output"])
        self.assertEqual(row["unk_token_count"], 64)
        self.assertEqual(row["decode_visibility"]["category"], "special_tokens_only")
        self.assertNotIn("token_ids", row)
        self.assertNotIn("output", row)

    def test_chinese_answer_and_no_raw_prompt_export(self):
        row = build_row("base", "control", 0, "用户：保密\n助手：", [2, 0], FakeTokenizer())
        self.assertTrue(row["contains_chinese"])
        self.assertFalse(row["blank_output"])
        self.assertEqual(row["safe_output_excerpt"], "[REDACTED: raw output withheld]")
        self.assertTrue(row["contains_chinese"])
        self.assertNotIn("好", str(row["safe_output_excerpt"]))
        self.assertNotIn("保密", str(row))

    def test_summary_rejects_noncomparable_control(self):
        data = rows()
        for r in data:
            if r["phase"] == "candidate" and r["setting"] == "control":
                r["punctuation_only"] = False
        self.assertFalse(summarize(data)["control_matches_previous_cpu_review"])


if __name__ == "__main__":
    unittest.main()
