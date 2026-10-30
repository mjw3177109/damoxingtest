"""Offline tests; do not download weights or allocate GPU."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run12_temperature_pair_cpu import generation_settings, summarize, verify_adapter


RUN12_CONFIG = {
    "base_model_name_or_path": "uer/gpt2-chinese-cluecorpussmall",
    "task_type": "CAUSAL_LM",
    "r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "fan_in_fan_out": True,
    "target_modules": ["c_attn", "c_proj"],
}


def write_config(folder, config=RUN12_CONFIG):
    (folder / "adapter_config.json").write_text(json.dumps(config), encoding="utf-8")


class FakeTokenizer:
    pad_token_id = 1
    eos_token_id = 2


class TemperaturePairTests(unittest.TestCase):
    def test_single_variable_changes_only_temperature(self):
        a = generation_settings(0.8, 64, FakeTokenizer())
        b = generation_settings(0.7, 64, FakeTokenizer())
        self.assertEqual({k: v for k, v in a.items() if k != "temperature"},
                         {k: v for k, v in b.items() if k != "temperature"})
        self.assertEqual((a["temperature"], b["temperature"]), (0.8, 0.7))
        self.assertTrue(a["do_sample"])

    def test_rejects_unregistered_temperature(self):
        with self.assertRaises(ValueError):
            generation_settings(1.0, 64, FakeTokenizer())

    def test_rejects_nonpositive_generation_length(self):
        with self.assertRaises(ValueError):
            generation_settings(0.8, 0, FakeTokenizer())

    def test_adapter_hash_and_config_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_config(folder)
            weights = b"test-adapter"
            (folder / "adapter_model.safetensors").write_bytes(weights)
            expected = hashlib.sha256(weights).hexdigest()
            self.assertEqual(verify_adapter(folder, expected), expected)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_adapter(folder)
            (folder / "adapter_config.json").unlink()
            with self.assertRaisesRegex(ValueError, "adapter_config"):
                verify_adapter(folder)

    def test_rejects_invalid_adapter_config_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "adapter_config.json").write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid adapter_config"):
                verify_adapter(folder)

    def test_rejects_wrong_adapter_recipe_before_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for change in ({"base_model_name_or_path": "wrong/model"},
                           {"task_type": "SEQ_CLS"}, {"r": 16},
                           {"lora_alpha": 32}, {"lora_dropout": 0.1},
                           {"fan_in_fan_out": False}):
                write_config(folder, {**RUN12_CONFIG, **change})
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, "pinned Run 12 recipe"):
                    verify_adapter(folder)

    def test_rejects_wrong_adapter_target_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for modules in (["c_attn"], ["c_attn", "c_proj", "lm_head"], "c_attn"):
                write_config(folder, {**RUN12_CONFIG, "target_modules": modules})
                with self.subTest(modules=modules), self.assertRaisesRegex(ValueError, "target modules"):
                    verify_adapter(folder)

    def test_missing_adapter_weights_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_config(folder)
            with self.assertRaisesRegex(ValueError, "safetensors"):
                verify_adapter(folder)

    def test_summary_requires_both_arms_and_no_automatic_quality_claim(self):
        def row(temp, punct, eos, index=0, digest="a" * 64):
            return dict(temperature=temp, prompt_index=index, prompt_sha256=digest,
                        punctuation_only=punct,
                        stop_reason_inferred="eos" if eos else "max_new_tokens",
                        longest_identical_character_run=4, generated_token_count=64)
        data = [row(0.8, True, False), row(0.7, False, True)]
        result = summarize(data)
        self.assertEqual(result["0.8"]["punctuation_only_count"], 1)
        self.assertEqual(result["0.7"]["eos_count"], 1)
        self.assertIsNone(result["0.7"]["direct_answer_count"])
        self.assertTrue(result["0.7"]["human_review_required"])
        with self.assertRaisesRegex(ValueError, "Missing comparison arm"):
            summarize(data[:1])


    def test_rejects_unpaired_prompt_indices(self):
        rows = [
            dict(temperature=0.8, prompt_index=0, prompt_sha256="a" * 64,
                 punctuation_only=True, stop_reason_inferred="eos",
                 longest_identical_character_run=4, generated_token_count=4),
            dict(temperature=0.7, prompt_index=1, prompt_sha256="b" * 64,
                 punctuation_only=False, stop_reason_inferred="eos",
                 longest_identical_character_run=4, generated_token_count=4),
        ]
        with self.assertRaisesRegex(ValueError, "Unpaired"):
            summarize(rows)

    def test_rejects_duplicate_prompt_in_one_arm(self):
        row = dict(prompt_index=0, prompt_sha256="a" * 64,
                   punctuation_only=False, stop_reason_inferred="eos",
                   longest_identical_character_run=2, generated_token_count=4)
        rows = [dict(row, temperature=0.8), dict(row, temperature=0.8),
                dict(row, temperature=0.7)]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            summarize(rows)

    def test_rejects_same_index_with_different_prompt_hash(self):
        row = dict(prompt_index=0, prompt_sha256="a" * 64,
                   punctuation_only=False, stop_reason_inferred="eos",
                   longest_identical_character_run=2, generated_token_count=4)
        rows = [dict(row, temperature=0.8),
                dict(row, temperature=0.7, prompt_sha256="b" * 64)]
        with self.assertRaisesRegex(ValueError, "Unpaired"):
            summarize(rows)

if __name__ == "__main__":
    unittest.main()
