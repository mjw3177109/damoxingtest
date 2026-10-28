"""Offline preflight for the production Kaggle workflow's embedded Bash.

Prevents a green Python-only CI from masking duplicated YAML steps or a
malformed shell tail. No credentials, Kaggle access, or GPU required.
"""
import re
import subprocess
import textwrap
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/daily-gpt2-training.yml"


def embedded_bash_scripts(source):
    lines = source.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^(\\s*)run:\\s*\\|\\s*$", line)
        if not match:
            continue
        key_indent = len(match.group(1))
        block = []
        for candidate in lines[index + 1:]:
            indent = len(candidate) - len(candidate.lstrip())
            if candidate.strip() and indent <= key_indent:
                break
            block.append(candidate)
        yield index + 1, textwrap.dedent("\n".join(block)) + "\n"


class WorkflowShellStructureTests(unittest.TestCase):
    def test_step_names_are_unique(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        names = re.findall(r"(?m)^\\s{6}- name:\\s*(.+)$", source)
        self.assertGreaterEqual(len(names), 8, "Expected the production workflow steps")
        self.assertEqual(len(names), len(set(names)), "Duplicate workflow step names")

    def test_embedded_bash_scripts_parse(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        scripts = list(embedded_bash_scripts(source))
        self.assertGreaterEqual(len(scripts), 4, "No Bash steps found")
        for line, script in scripts:
            with self.subTest(run_line=line):
                result = subprocess.run(
                    ["bash", "-n"], input=script, text=True,
                    capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
