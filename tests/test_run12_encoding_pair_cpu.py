"""Offline tests for CPU-only Run 12 paired prompt encoding audit."""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_encoding_pair_cpu import ARMS, generation_kwargs, summarize


class FakeTokenizer:
    pad_token_id = 0
    eos_token_id = 102


def sample(arm, index, digest=None):
    digest = digest or hashlib.sha256(str(index).encode()).hexdigest()
    return {
        "arm": arm, "prompt_index": index, "prompt_sha256": digest,
        "input_token_id_sha256": "a" * 64 if arm == ARMS[0] else "b" * 64,
        "output_token_id_sha256": "c" * 64,
        "punctuation_only": False, "stop_reason_inferred": "eos",
        "longest_identical_character_run": 2, "generated_token_count": 4,
    }


def paired():
    return [sample(arm, index) for index in range(10) for arm in ARMS]


class EncodingPairTests(unittest.TestCase):
    def test_greedy_settings_match_historical_generation(self):
        self.assertEqual(generation_kwargs(FakeTokenizer()), {
            "max_new_tokens": 64, "do_sample": False, "repetition_penalty": 1.12,
            "pad_token_id": 0, "eos_token_id": 102})

    def test_nonpositive_length_rejected(self):
        with self.assertRaises(ValueError):
            generation_kwargs(FakeTokenizer(), 0)

    def test_summary_is_paired_and_never_approves(self):
        result = summarize(paired())
        self.assertEqual(result["paired_input_id_differences"], 10)
        self.assertEqual(result["paired_output_id_differences"], 0)
        for arm in ARMS:
            self.assertEqual(result[arm]["samples"], 10)
            self.assertIsNone(result[arm]["direct_answer_count"])
            self.assertTrue(result[arm]["human_review_required"])

    def test_rejects_missing_or_duplicate_prompt(self):
        rows = paired()
        with self.assertRaises(ValueError):
            summarize(rows[:-1])
        with self.assertRaises(ValueError):
            summarize(rows[:-1] + [rows[0]])

    def test_rejects_unpaired_content_hash(self):
        rows = paired()
        rows[1] = {**rows[1], "prompt_sha256": "f" * 64}
        with self.assertRaisesRegex(ValueError, "Unpaired"):
            summarize(rows)

    def test_rejects_invalid_prompt_provenance(self):
        rows = paired()
        rows[0] = {**rows[0], "prompt_sha256": "invalid"}
        with self.assertRaisesRegex(ValueError, "provenance"):
            summarize(rows)


if __name__ == "__main__":
    unittest.main()
