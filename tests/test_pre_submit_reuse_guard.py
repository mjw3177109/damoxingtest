"""Offline contract tests for the no-GPU, pre-submit reuse path."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pre_submit_reuse_guard as guard
from pre_submit_reuse_guard import has_completed_same_data_run, materialize_skip


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


class SameDataRetrainApprovalTests(unittest.TestCase):
    """No-GPU fixtures for the guard that protects recipe-only changes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "data/train.jsonl"
        self.holdout = self.root / "data/eval.jsonl"
        self.data.parent.mkdir(parents=True)
        self.data.write_text('{"instruction":"A","response":"B"}\n', encoding="utf-8")
        self.holdout.write_text('{"instruction":"C","response":"D"}\n', encoding="utf-8")
        self.source = self.root / "reports/2026-10-23/run-123"
        self.source.mkdir(parents=True)
        (self.source / "run_metadata.json").write_text(json.dumps({
            "training_data_sha256": hashlib.sha256(self.data.read_bytes()).hexdigest(),
            "eval_data_sha256": hashlib.sha256(self.holdout.read_bytes()).hexdigest(),
            "training_recipe_sha256": "historical-recipe-sha",
        }), encoding="utf-8")
        self.status({"status": "completed"})

    def status(self, payload):
        (self.source / "training_status.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def matched(self):
        return has_completed_same_data_run(
            "data/train.jsonl", "data/eval.jsonl", repo_root=self.root
        )

    def test_completed_same_data_requires_approval_when_exact_reuse_fails(self):
        self.assertTrue(self.matched())

    def test_changed_data_does_not_trigger_same_data_block(self):
        self.holdout.write_text('{"instruction":"new","response":"data"}\n',
                                encoding="utf-8")
        self.assertFalse(self.matched())

    def test_skipped_historical_run_is_not_completed_training_evidence(self):
        self.status({"status": "completed", "skipped_no_changes": True})
        self.assertFalse(self.matched())

    def test_failed_historical_run_is_not_completed_training_evidence(self):
        self.status({"status": "failed"})
        self.assertFalse(self.matched())

    def test_cli_blocks_without_dispatch_approval(self):
        run_dir = self.root / "reports/2026-10-25/run-456"
        github_output = self.root / "github-output.txt"
        argv = ["guard", "--run-dir", str(run_dir), "--github-output", str(github_output)]
        with patch.object(sys, "argv", argv), \
             patch.object(guard, "find_reusable_run", return_value=None), \
             patch.object(guard, "has_completed_same_data_run", return_value=True):
            guard.main()
        self.assertEqual((run_dir / "status.txt").read_text().strip(),
                         "BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL")
        self.assertIn("blocked=true", github_output.read_text())
        self.assertIn("reuse=false", github_output.read_text())
        self.assertFalse((run_dir / "kaggle_output").exists())

    def test_cli_explicit_approval_allows_guarded_path(self):
        run_dir = self.root / "reports/2026-10-25/run-456"
        github_output = self.root / "github-output.txt"
        argv = ["guard", "--run-dir", str(run_dir), "--github-output",
                str(github_output), "--approve-same-data-retrain"]
        with patch.object(sys, "argv", argv), \
             patch.object(guard, "find_reusable_run", return_value=None):
            guard.main()
        self.assertIn("blocked=false", github_output.read_text())
        self.assertIn("reuse=false", github_output.read_text())
        self.assertFalse((run_dir / "status.txt").exists())

    def test_workflow_guards_every_kaggle_submit_step(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/daily-gpt2-training.yml").read_text(encoding="utf-8")
        self.assertIn("approve_same_data_retrain:", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertEqual(workflow.count(
            "steps.reuse_guard.outputs.blocked != 'true'"), 4)
        self.assertIn("--approve-same-data-retrain", workflow)


if __name__ == "__main__":
    unittest.main()
