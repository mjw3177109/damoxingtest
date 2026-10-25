"""Offline regression tests: do not reuse a run after training config changes."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import train_gpt2_lora as training


def historical_metadata():
    return {
        "model_name": training.MODEL_DEFAULT,
        "seed": 42,
        "max_length": 256,
        "epochs": 3,
        "learning_rate": 0.0002,
        "per_device_train_batch_size": 2,
        "gradient_accumulation_steps": 2,
        "lora_rank": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
    }


class TrainingReuseConfigTests(unittest.TestCase):
    def test_matching_defaults_allow_reuse(self):
        self.assertTrue(training.reusable_training_config_matches(
            historical_metadata(), SimpleNamespace()
        ))

    def test_changed_learning_rate_rejects_reuse(self):
        self.assertFalse(training.reusable_training_config_matches(
            historical_metadata(), SimpleNamespace(learning_rate=0.0001)
        ))

    def test_changed_model_or_batch_rejects_reuse(self):
        for override in ({"model_name": "different/base"}, {"batch_size": 4}):
            with self.subTest(override=override):
                self.assertFalse(training.reusable_training_config_matches(
                    historical_metadata(), SimpleNamespace(**override)
                ))

    def test_changed_lora_or_seed_rejects_reuse(self):
        for override in ({"lora_rank": 16}, {"seed": 123}):
            with self.subTest(override=override):
                self.assertFalse(training.reusable_training_config_matches(
                    historical_metadata(), SimpleNamespace(**override)
                ))

    def test_requested_prior_adapter_rejects_base_run(self):
        self.assertFalse(training.reusable_training_config_matches(
            historical_metadata(), SimpleNamespace(adapter_path="approved/adapter")
        ))

    def test_missing_metadata_fails_closed(self):
        metadata = historical_metadata()
        metadata.pop("learning_rate")
        self.assertFalse(training.reusable_training_config_matches(
            metadata, SimpleNamespace()
        ))

    def test_find_reusable_run_integration_checks_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "scripts").mkdir()
            (root / "data").mkdir()
            for path in ("scripts/train_gpt2_lora.py", "kaggle/gpt2_training.ipynb",
                         "requirements-kaggle.txt"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fixture", encoding="utf-8")
            train = root / "data/train.jsonl"
            evaluation = root / "data/eval.jsonl"
            train.write_text('{"instruction":"A","response":"B"}\n', encoding="utf-8")
            evaluation.write_text('{"instruction":"C","response":"D"}\n', encoding="utf-8")
            source = root / "reports/2026-10-23/run-123"
            source.mkdir(parents=True)
            metadata = historical_metadata()
            metadata["training_data_sha256"] = hashlib.sha256(train.read_bytes()).hexdigest()
            metadata["eval_data_sha256"] = hashlib.sha256(evaluation.read_bytes()).hexdigest()
            with patch.object(training, "__file__", str(root / "scripts/train_gpt2_lora.py")):
                metadata["training_recipe_sha256"] = training.training_recipe_hash()
                (source / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
                (source / "training_status.json").write_text(
                    '{"status":"completed"}', encoding="utf-8"
                )
                (source / "metrics.json").write_text("{}", encoding="utf-8")
                (source / "samples.json").write_text(
                    json.dumps([{"output": "fixture"}] * 10), encoding="utf-8"
                )
                args = SimpleNamespace(data="data/train.jsonl",
                                       eval_data="data/eval.jsonl", force_retrain=False)
                self.assertIsNotNone(training.find_reusable_run(args))
                args.learning_rate = 0.0001
                self.assertIsNone(training.find_reusable_run(args))


if __name__ == "__main__":
    unittest.main()
