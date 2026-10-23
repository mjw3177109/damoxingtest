import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from analyze_generation_samples import inspect_outputs, longest_run


class GenerationDiagnosticsTests(unittest.TestCase):
    def test_run_lengths(self):
        self.assertEqual(longest_run(""), 0)
        self.assertEqual(longest_run("abbbbcc"), 4)

    def test_punctuation_collapse(self):
        samples = [{"prompt": "private prompt", "output": "." * 64} for _ in range(9)]
        samples.append({"output": "?" * 64})
        report = inspect_outputs(samples, "test")
        self.assertEqual(report["sample_count"], 10)
        self.assertEqual(report["punctuation_only_count"], 10)
        self.assertEqual(report["single_character_repeated_count"], 10)
        self.assertEqual(report["unique_output_count"], 2)
        self.assertEqual(report["longest_identical_character_run"], 64)
        self.assertNotIn("private prompt", str(report))

    def test_chinese_and_empty(self):
        report = inspect_outputs([{"output": "保护用户。"}, {"output": "  "}])
        self.assertEqual(report["empty_output_count"], 1)
        self.assertEqual(report["punctuation_only_count"], 0)
        self.assertEqual(report["single_character_repeated_count"], 0)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            inspect_outputs({"output": "hello"})
        with self.assertRaises(ValueError):
            inspect_outputs([{"output": None}])


if __name__ == "__main__":
    unittest.main()
