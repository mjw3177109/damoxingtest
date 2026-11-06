"""CPU-only tests for exact Git checkout provenance; no Kaggle or model downloads."""
import unittest
from types import SimpleNamespace
from unittest import mock

from scripts import train_gpt2_lora


class SourceGitShaTests(unittest.TestCase):
    def test_valid_checkout_sha_is_recorded(self):
        sha = "abcdef0123456789abcdef0123456789abcdef01"
        with mock.patch.object(train_gpt2_lora.subprocess, "run",
                               return_value=SimpleNamespace(stdout=sha + "\n")):
            self.assertEqual(train_gpt2_lora.source_git_commit_sha(), sha)

    def test_git_unavailable_fails_closed(self):
        with mock.patch.object(train_gpt2_lora.subprocess, "run",
                               side_effect=FileNotFoundError("git not installed")):
            self.assertIsNone(train_gpt2_lora.source_git_commit_sha())

    def test_malformed_git_output_fails_closed(self):
        with mock.patch.object(train_gpt2_lora.subprocess, "run",
                               return_value=SimpleNamespace(stdout="not-a-sha\n")):
            self.assertIsNone(train_gpt2_lora.source_git_commit_sha())


if __name__ == "__main__":
    unittest.main()
