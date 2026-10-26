"""Offline adapter integrity audit regressions, no torch/GPU/network."""

import json
import math
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.adapter_tensor_integrity_audit import audit_archive, audit_safetensors


def tensor_bytes(values, offsets=None):
    raw = struct.pack("<" + "f" * len(values), *values)
    header = {"example.lora_A.weight": {
        "dtype": "F32", "shape": [len(values)],
        "data_offsets": offsets if offsets is not None else [0, len(raw)],
    }}
    encoded = json.dumps(header).encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded + raw


class AdapterTensorIntegrityAuditTests(unittest.TestCase):
    def test_finite_nonzero_tensor(self):
        result = audit_safetensors(tensor_bytes([0.0, 3.0, 4.0]))
        self.assertEqual(result["tensor_count"], 1)
        self.assertEqual(result["parameter_count"], 3)
        self.assertEqual(result["nonfinite_value_count"], 0)
        self.assertEqual(result["all_zero_tensor_count"], 0)
        self.assertAlmostEqual(result["max_tensor_l2_norm"], 5.0)

    def test_nonfinite_and_zero_tensor_detection(self):
        self.assertEqual(audit_safetensors(tensor_bytes([0.0, 0.0]))["all_zero_tensor_count"], 1)
        self.assertFalse(audit_safetensors(tensor_bytes([1.0, float("nan")]))["all_values_finite"])

    def test_bad_header_or_offsets_fail_closed(self):
        with self.assertRaises(ValueError):
            audit_safetensors(b"broken")
        with self.assertRaises(ValueError):
            audit_safetensors(tensor_bytes([1.0], offsets=[0, 8]))

    def test_zip_audit_is_aggregate_only(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "artifact.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("reports/run/kaggle_output/training_output/adapter/adapter_model.safetensors", tensor_bytes([1.0]))
            result = audit_archive(archive_path)
            self.assertEqual(result["parameter_count"], 1)
            self.assertEqual(len(result["adapter_sha256"]), 64)
            self.assertNotIn("example.lora_A.weight", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
