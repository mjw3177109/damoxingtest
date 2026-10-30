"""Offline tests for the privacy-safe Run 12 exact-input CPU experiment."""
import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location(
    "run12_train_exact_pair_cpu", TOOLS / "run12_train_exact_pair_cpu.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rows():
    result = []
    for arm in module.ARMS:
        for index in range(10):
            result.append({
                "arm": arm,
                "prompt_index": index,
                "prompt_sha256": f"{index + 1:064x}",
                "input_token_count": 12 if arm == "train_parity" else 10,
                "input_token_id_sha256": f"{index + (1 if arm == 'train_parity' else 20):064x}",
                "output_token_id_sha256": f"{index + 50:064x}",
                "generated_token_count": 64,
                "eos_position": None,
                "stop_reason_inferred": "max_new_tokens",
                "character_count": 64,
                "distinct_characters": 12,
                "longest_identical_character_run": 2,
                "punctuation_only": False,
            })
    return result


class ExactInputPairTests(unittest.TestCase):
    def test_complete_pairs_and_input_difference(self):
        summary = module.summarize(rows())
        self.assertEqual(summary["paired_input_id_differences"], 10)
        self.assertEqual(summary["paired_output_id_differences"], 0)
        self.assertEqual(summary["train_exact"]["punctuation_only_count"], 0)
        self.assertIsNone(summary["train_exact"]["direct_answer_count"])

    def test_incomplete_pairs_rejected(self):
        with self.assertRaisesRegex(ValueError, "Exactly 20"):
            module.summarize(rows()[:-1])

    def test_duplicate_pair_rejected(self):
        sample = rows()
        sample[-1]["prompt_index"] = 0
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            module.summarize(sample)

    def test_mismatched_prompt_digest_rejected(self):
        sample = rows()
        sample[-1]["prompt_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "Prompt content"):
            module.summarize(sample)

    def test_raw_output_field_rejected(self):
        sample = rows()
        sample[0]["output"] = "private generated text"
        with self.assertRaisesRegex(ValueError, "privacy-unsafe"):
            module.summarize(sample)

    def test_raw_token_ids_field_rejected(self):
        sample = rows()
        sample[0]["token_ids"] = [1, 2]
        with self.assertRaisesRegex(ValueError, "privacy-unsafe"):
            module.summarize(sample)

    def test_invalid_digest_rejected(self):
        sample = rows()
        sample[0]["input_token_id_sha256"] = "invalid"
        with self.assertRaisesRegex(ValueError, "token digest"):
            module.summarize(sample)

    def test_boolean_prompt_index_rejected(self):
        sample = rows()
        sample[0]["prompt_index"] = True
        with self.assertRaisesRegex(ValueError, "Invalid arm"):
            module.summarize(sample)


if __name__ == "__main__":
    unittest.main()
