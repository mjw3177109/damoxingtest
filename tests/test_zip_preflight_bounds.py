"""Bounded ZIP preflight tests: reject resource-heavy archives before decompression."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_adapter_artifact.py"
spec = importlib.util.spec_from_file_location("audit_adapter_zip_limits", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BoundedZipPreflightTests(unittest.TestCase):
    def make_zip(self, contents):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        archive = Path(tmp.name) / "artifact.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in contents:
                zf.writestr(name, data)
        return archive

    def test_rejects_excessive_member_count(self):
        archive = self.make_zip([("a", b"1"), ("b", b"2")])
        with mock.patch.object(module, "MAX_ARCHIVE_MEMBERS", 1):
            with mock.patch.object(zipfile.ZipFile, "testzip", side_effect=AssertionError("decompressed too early")):
                with self.assertRaisesRegex(ValueError, "member count"):
                    module.audit_artifact(archive, "synthetic")

    def test_rejects_large_single_member_before_integrity_scan(self):
        archive = self.make_zip([("large", b"0123456789")])
        with mock.patch.object(module, "MAX_ARCHIVE_MEMBER_BYTES", 5):
            with mock.patch.object(zipfile.ZipFile, "testzip", side_effect=AssertionError("decompressed too early")):
                with self.assertRaisesRegex(ValueError, "member exceeds"):
                    module.audit_artifact(archive, "synthetic")

    def test_rejects_oversized_total_before_integrity_scan(self):
        archive = self.make_zip([("a", b"1234"), ("b", b"5678")])
        with mock.patch.object(module, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 7):
            with mock.patch.object(zipfile.ZipFile, "testzip", side_effect=AssertionError("decompressed too early")):
                with self.assertRaisesRegex(ValueError, "total uncompressed"):
                    module.audit_artifact(archive, "synthetic")

    def test_small_archive_still_scans_normally(self):
        archive = self.make_zip([("notes.txt", b"safe")])
        result = module.audit_artifact(archive, "synthetic")
        self.assertEqual(result["archive_integrity"], "passed")
        self.assertFalse(result["candidate_recoverable"])
        self.assertFalse(result["approval_verified"])


if __name__ == "__main__":
    unittest.main()
