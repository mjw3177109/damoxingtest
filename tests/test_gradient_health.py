"""Offline gradient log audit tests: no network, model, GPU, or credentials."""
import importlib.util
import math
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_gradient_health.py"
spec = importlib.util.spec_from_file_location("audit_gradient_health", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GradientHealthTests(unittest.TestCase):
    def test_realistic_trainer_entries_are_aggregated_without_raw_log(self):
        log = ("2026-10-23 | INFO | Trainer metrics at step 1: {'loss': 3.38, 'grad_norm': 39550.09375, 'learning_rate': 0.0001}\n"
               "2026-10-23 | INFO | Trainer metrics at step 5: {'loss': 3.41, 'grad_norm': 41631.30078125}\n")
        result = module.audit_log(log)
        self.assertEqual(result["gradient_norm_observations"], 2)
        self.assertEqual(result["observed_steps"], [1, 5])
        self.assertEqual(result["logged_norm_above_threshold_count"], 2)
        self.assertEqual(result["logged_norm_max"], 41631.30078125)
        self.assertNotIn("loss", str(result))
        self.assertFalse(result["promotion_approved"])

    def test_nonfinite_gradient_norm_is_flagged_without_claiming_root_cause(self):
        result = module.audit_log("Trainer metrics at step 3: {'grad_norm': nan}\nTrainer metrics at step 4: {'grad_norm': 0.5}")
        self.assertEqual(result["nonfinite_gradient_steps"], [3])
        self.assertEqual(result["logged_norm_max"], 0.5)
        self.assertIn("before clipping", result["interpretation"])

    def test_missing_or_malformed_entries_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "No Trainer"):
            module.audit_log("Trainer metrics at step 3: {'eval_loss': 2.0}")
        with self.assertRaisesRegex(ValueError, "Unparseable"):
            module.audit_log("Trainer metrics at step 3: {'grad_norm': something}")

    def test_invalid_threshold_is_rejected(self):
        for value in (0.0, -1.0, math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.audit_log("Trainer metrics at step 1: {'grad_norm': 1.0}", value)


if __name__ == "__main__":
    unittest.main()
