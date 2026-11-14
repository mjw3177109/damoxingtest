"""Offline regression tests for Run 12 reference-overlap CPU diagnostic."""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_reference_overlap_cpu import ARMS, char_bigram_f1, measure, summarize


def row(arm, index):
    return {
        "arm": arm, "prompt_index": index,
        "prompt_sha256": hashlib.sha256(str(index).encode()).hexdigest(),
        "char_bigram_f1": 0.25 if arm == "base" else 0.5,
        "empty_output": False, "cjk_char_count": 4,
        "punctuation_only": False, "stop_reason_inferred": "eos",
    }


def paired():
    return [row(arm, i) for i in range(10) for arm in ARMS]


class ReferenceOverlapTests(unittest.TestCase):
    def test_exact_bigrams(self):
        self.assertEqual(char_bigram_f1("abc", "abc"), 1.0)
        self.assertEqual(char_bigram_f1("ab", "xy"), 0.0)
        self.assertEqual(char_bigram_f1("", "abc"), 0.0)

    def test_empty_and_punctuation(self):
        self.assertTrue(measure("", "参考")["empty_output"])
        self.assertTrue(measure("。。。", "参考")["punctuation_only"])
        self.assertEqual(measure("保护用户", "参考")["cjk_char_count"], 4)

    def test_summary_and_no_automatic_approval(self):
        s = summarize(paired())
        self.assertEqual(s["candidate_minus_base_bigram_f1"], 0.25)
        self.assertIsNone(s["run12_candidate"]["direct_answer_count"])
        self.assertTrue(s["run12_candidate"]["human_review_required"])

    def test_reject_missing_duplicate(self):
        with self.assertRaises(ValueError):
            summarize(paired()[:-1])
        r = paired()
        with self.assertRaises(ValueError):
            summarize(r[:-1] + [r[0]])

    def test_reject_unpaired_hash(self):
        r = paired()
        r[1]["prompt_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "Unpaired"):
            summarize(r)

    def test_reject_invalid_index(self):
        r = paired()
        r[0]["prompt_index"] = True
        with self.assertRaises(ValueError):
            summarize(r)


if __name__ == "__main__":
    unittest.main()
