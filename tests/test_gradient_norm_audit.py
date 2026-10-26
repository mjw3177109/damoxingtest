"""CPU-only gradient log diagnostic regression tests."""
import json
import unittest

from tools.gradient_norm_audit import audit_log


class GradientNormAuditTests(unittest.TestCase):
    def test_valid_realistic_metrics_and_privacy(self):
        secret = "DO-NOT-PRINT-PROMPT"
        raw = (f"secret {secret}\n"
               "Trainer metrics at step 1: {'loss': 3.38, 'grad_norm': 39550.09375, 'epoch': 0.1}\n"
               "Trainer metrics at step 5: {'loss': 3.41, 'grad_norm': 41631.3}\n"
               "Trainer metrics at step 11: {'eval_loss': 3.28}\n")
        result = audit_log(raw)
        self.assertEqual(result["gradient_record_count"], 2)
        self.assertEqual(result["first_step"], 1)
        self.assertEqual(result["last_step"], 5)
        self.assertEqual(result["count_above_configured_max_grad_norm"], 2)
        self.assertFalse(result["promotion_approved"])
        self.assertNotIn(secret, json.dumps(result))
        self.assertIn("do not prove", result["interpretation"])

    def test_no_metrics_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "No actual Trainer"):
            audit_log("Trainer metrics at step 1: {'eval_loss': 3.1}")

    def test_nonfinite_and_negative_fail_closed(self):
        for bad in ("float('nan')", "-1", "'not-number'", "True"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    audit_log("Trainer metrics at step 1: {'grad_norm': " + bad + "}")

    def test_duplicate_or_out_of_order_steps_rejected(self):
        for second in (1, 0):
            raw = ("Trainer metrics at step 1: {'grad_norm': 5}\n"
                   f"Trainer metrics at step {second}: {{'grad_norm': 6}}\n")
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                audit_log(raw)

    def test_invalid_clipping_threshold(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                audit_log("Trainer metrics at step 1: {'grad_norm': 2}", value)


if __name__ == "__main__":
    unittest.main()
