"""Synthetic safetensors header validation; no network, model execution or GPU."""
import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_adapter_artifact.py"
spec = importlib.util.spec_from_file_location("audit_adapter_header", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_safetensors(header=None, payload=b"\x00\x00\x00\x00"):
    if header is None:
        header = {"lora_A.weight": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}
    raw = json.dumps(header).encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw + payload


class HeaderAuditTests(unittest.TestCase):
    def candidate(self, weights):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        archive = Path(tmp.name) / "artifact.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("run/adapter/adapter_model.safetensors", weights)
            zf.writestr("run/adapter/adapter_config.json", '{"base_model_name_or_path":"base/model"}')
        return archive

    def test_valid_header_is_candidate_not_approved(self):
        result = module.audit_artifact(self.candidate(make_safetensors()), "123", "base/model")
        self.assertTrue(result["candidate_recoverable"])
        self.assertEqual(result["tensor_count"], 1)
        self.assertEqual(result["safetensors_header_check"], "passed")
        self.assertFalse(result["approval_verified"])

    def test_arbitrary_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, "safetensors"):
            module.audit_artifact(self.candidate(b"test-weights"), "123")

    def test_huge_header_rejected_before_read(self):
        with self.assertRaisesRegex(ValueError, "header length"):
            module.audit_artifact(self.candidate(struct.pack("<Q", module.MAX_SAFETENSORS_HEADER_BYTES + 1) + b"{}"), "123")

    def test_tensor_offsets_out_of_bounds(self):
        header = {"weight": {"dtype": "F32", "shape": [1], "data_offsets": [0, 100]}}
        with self.assertRaisesRegex(ValueError, "offsets"):
            module.audit_artifact(self.candidate(make_safetensors(header)), "123")

    def test_tensor_size_mismatch(self):
        header = {"weight": {"dtype": "F32", "shape": [2], "data_offsets": [0, 4]}}
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            module.audit_artifact(self.candidate(make_safetensors(header)), "123")

    def test_overlapping_ranges(self):
        header = {"a": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]},
                  "b": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}
        with self.assertRaisesRegex(ValueError, "overlap"):
            module.audit_artifact(self.candidate(make_safetensors(header)), "123")

    def test_no_tensors_rejected(self):
        with self.assertRaisesRegex(ValueError, "no tensors"):
            module.audit_artifact(self.candidate(make_safetensors({})), "123")

    def test_base_model_mismatch_still_blocks(self):
        result = module.audit_artifact(self.candidate(make_safetensors()), "123", "other/model")
        self.assertFalse(result["candidate_recoverable"])
        self.assertFalse(result["approval_verified"])


if __name__ == "__main__":
    unittest.main()
