"""Offline, read-only ZIP artifact checks. No model load, GPU or credentials."""
import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_adapter_artifact.py"
spec = importlib.util.spec_from_file_location("audit_adapter_artifact", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_safetensors():
    header = json.dumps({"weight": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
    return struct.pack("<Q", len(header)) + header + b"\0" * 4


class AdapterArtifactAuditTests(unittest.TestCase):
    def make_zip(self, entries):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "artifact.zip"
        with zipfile.ZipFile(path, "w") as zf:
            for name, content in entries:
                zf.writestr(name, content)
        return path

    def test_complete_candidate_is_not_approved(self):
        path = self.make_zip([
            ("run/kaggle_output/training_output/adapter/adapter_model.safetensors", b"test-weights"),
            ("run/kaggle_output/training_output/adapter/adapter_config.json", b"{}"),
        ])
        result = module.audit_artifact(path, "123")
        self.assertTrue(result["candidate_recoverable"])
        self.assertFalse(result["approval_verified"])
        self.assertEqual(result["adapter_bytes"], len(weights))

    def test_missing_config_is_not_recoverable(self):
        path = self.make_zip([("run/adapter/adapter_model.safetensors", b"test")])
        self.assertFalse(module.audit_artifact(path, "123")["candidate_recoverable"])

    def test_duplicate_adapter_is_ambiguous(self):
        path = self.make_zip([
            ("a/adapter/adapter_model.safetensors", b"a"),
            ("a/adapter/adapter_config.json", b"{}"),
            ("b/adapter/adapter_model.safetensors", b"b"),
            ("b/adapter/adapter_config.json", b"{}"),
        ])
        self.assertFalse(module.audit_artifact(path, "123")["candidate_recoverable"])

    def test_traversal_path_rejected(self):
        path = self.make_zip([("../adapter/adapter_model.safetensors", b"a")])
        with self.assertRaisesRegex(ValueError, "unsafe"):
            module.audit_artifact(path, "123")

    def test_empty_weights_rejected(self):
        path = self.make_zip([
            ("a/adapter/adapter_model.safetensors", b""),
            ("a/adapter/adapter_config.json", b"{}"),
        ])
        with self.assertRaisesRegex(ValueError, "empty"):
            module.audit_artifact(path, "123")


if __name__ == "__main__":
    unittest.main()
