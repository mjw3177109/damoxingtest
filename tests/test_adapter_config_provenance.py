"""Bounded adapter config provenance checks on synthetic ZIP files only."""
import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_adapter_artifact.py"
spec = importlib.util.spec_from_file_location("audit_adapter_artifact_provenance", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_safetensors():
    header = json.dumps({"weight": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
    return struct.pack("<Q", len(header)) + header + b"\\0" * 4


class AdapterConfigProvenanceTests(unittest.TestCase):
    def candidate(self, config):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        archive = Path(temp.name) / "candidate.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("run/adapter/adapter_model.safetensors", fake_safetensors())
            zf.writestr("run/adapter/adapter_config.json", config)
        return archive

    def test_matching_base_model_is_verified_not_approved(self):
        result = module.audit_artifact(self.candidate(b'{"base_model_name_or_path":"base/model"}'), "run", "base/model")
        self.assertEqual(result["base_model_check"], "matched")
        self.assertTrue(result["candidate_recoverable"])
        self.assertFalse(result["approval_verified"])

    def test_mismatch_blocks_candidate_and_does_not_echo_model_id(self):
        result = module.audit_artifact(self.candidate(b'{"base_model_name_or_path":"private/model"}'), "run", "base/model")
        self.assertEqual(result["base_model_check"], "mismatched")
        self.assertFalse(result["candidate_recoverable"])
        self.assertNotIn("private/model", str(result))

    def test_missing_model_metadata_fails_when_expected(self):
        result = module.audit_artifact(self.candidate(b'{}'), "run", "base/model")
        self.assertEqual(result["base_model_check"], "missing")
        self.assertFalse(result["candidate_recoverable"])

    def test_malformed_json_rejected(self):
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            module.audit_artifact(self.candidate(b'{bad'), "run")

    def test_scalar_json_rejected(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            module.audit_artifact(self.candidate(b'[]'), "run")

    def test_oversized_config_rejected(self):
        with self.assertRaisesRegex(ValueError, "size limit"):
            module.audit_artifact(self.candidate(b" " * (module.MAX_CONFIG_BYTES + 1)), "run")

    def test_invalid_model_metadata_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid base model"):
            module.audit_artifact(self.candidate(b'{"base_model_name_or_path":23}'), "run")


if __name__ == "__main__":
    unittest.main()
