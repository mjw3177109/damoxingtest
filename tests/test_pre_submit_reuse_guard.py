"""Offline contract tests for the no-GPU, pre-submit reuse path."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pre_submit_reuse_guard import materialize_skip


class PreSubmitReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "reports" / "2026-10-23" / "run-123"
        self.source.mkdir(parents=True)
        self.run = self.root / "reports" / "2026-10-24" / "run-456"
        self.run.mkdir(parents=True)
        self.put("metrics.json", {
            "training_data_sha256": "train-sha", "eval_data_sha256": "eval-sha",
            "train_steps": 33, "train_loss": 3.2, "gpu_name": "Tesla T4",
            "gpu_memory_gib": 14.56, "final_eval_loss": 3.1,
        })
        self.put("run_metadata.json", {
            "gpu_name": "Tesla T4", "gpu_memory_gib": 14.56,
            "cuda_available": True, "started_at_utc": "historical",
        })
        self.put("samples.json", [{"output": "..."}] * 10)
        self.put("training_status.json", {"status": "completed"})
        (self.source / "summary.md").write_text("Historical GPU training\n", encoding="utf-8")

    def put(self, name, payload):
        (self.source / name).write_text(json.dumps(payload), encoding="utf-8")

    def result(self, name):
        return json.loads((self.run / "kaggle_output" / "training_output" / name).read_text(encoding="utf-8"))

    def test_no_new_training_or_metrics_claim_and_source_preserved(self):
        original = (self.source / "metrics.json").read_bytes()
        origin = materialize_skip(self.source, self.run, repo_root=self.root)
        self.assertEqual(origin, "reports/2026-10-23/run-123")
        metrics = self.result("metrics.json")
        self.assertEqual(metrics["train_steps"], 0)
        self.assertIsNone(metrics["train_loss"])
        self.assertIsNone(metrics["gpu_name"])
        self.assertEqual(metrics["final_eval_loss"], 3.1)
        self.assertIn("historical", metrics["interpretation"])
        self.assertEqual((self.source / "metrics.json").read_bytes(), original)
        self.assertEqual((self.run / "status.txt").read_text().strip(), "PRE_SUBMIT_SKIPPED_NO_CHANGES")

    def test_no_gpu_kernel_claim_and_clean_log(self):
        materialize_skip(self.source, self.run, repo_root=self.root)
        status = self.result("training_status.json")
        metadata = self.result("run_metadata.json")
        self.assertTrue(status["skipped_no_changes"])
        self.assertFalse(status["kaggle_kernel_submitted"])
        self.assertFalse(metadata["current_run_performed_gpu_training"])
        self.assertEqual(metadata["source_run_gpu_name"], "Tesla T4")
        self.assertIsNone(metadata["gpu_name"])
        self.assertEqual(metadata["source_run_started_at_utc"], "historical")
        log = (self.run / "kaggle_output" / "training_output" / "training.log").read_text()
        self.assertIn("no Kaggle submission", log)
        self.assertNotIn("Historical GPU training", log)

    def test_reject_incomplete_or_previously_skipped_source(self):
        self.put("training_status.json", {"status": "completed", "skipped_no_changes": True})
        with self.assertRaises(ValueError):
            materialize_skip(self.source, self.run, repo_root=self.root)
        self.put("training_status.json", {"status": "completed"})
        (self.source / "summary.md").unlink()
        with self.assertRaises(ValueError):
            materialize_skip(self.source, self.run, repo_root=self.root)

    def test_reject_missing_data_hashes_or_samples(self):
        self.put("metrics.json", {"final_eval_loss": 3.1})
        with self.assertRaises(ValueError):
            materialize_skip(self.source, self.run, repo_root=self.root)
        self.put("metrics.json", {"training_data_sha256": "x", "eval_data_sha256": "y"})
        self.put("samples.json", [{"output": "..."}])
        with self.assertRaises(ValueError):
            materialize_skip(self.source, self.run, repo_root=self.root)


if __name__ == "__main__":
    unittest.main()
