"""Execute the terminal-failure Kaggle shell branch with a fake CLI.

This is a zero-network, zero-GPU regression test: a terminal failure must
never call `kaggle kernels push`, even when the shell step itself exits 0.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-gpt2-training.yml"


def launch_shell_script():
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.strip() == "- name: Launch, monitor, and download")
    run_line = next(i for i in range(start + 1, len(lines))
                    if lines[i].strip() == "run: |")
    body = []
    for line in lines[run_line + 1:]:
        if line and not line.startswith("          "):
            break
        body.append(line[10:] if line else "")
    if not body:
        raise AssertionError("Kaggle launch shell script was not found")
    return "\n".join(body) + "\n"


class TerminalRetryShellExecutionTests(unittest.TestCase):
    def test_terminal_states_cannot_reach_kaggle_push(self):
        script = launch_shell_script()
        for status in (
            "KernelWorkerStatus.ERROR",
            "Status: ERROR",
            "KernelWorkerStatus.FAILED",
            "Status: FAILED",
            "KernelWorkerStatus.CANCELLED",
            "Status: CANCELLED",
        ):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bin_dir = root / "bin"
                bin_dir.mkdir()
                run_dir = root / "run"
                run_dir.mkdir()
                push_marker = root / "unexpected_push"
                fake_kaggle = bin_dir / "kaggle"
                fake_kaggle.write_text(
                    '#!/usr/bin/env bash\n'
                    'if [[ "$1" == "kernels" && "$2" == "status" ]]; then\n'
                    '  printf "%s\\n" "$TEST_KERNEL_STATUS"\n'
                    '  exit 0\n'
                    'fi\n'
                    'if [[ "$1" == "kernels" && "$2" == "push" ]]; then\n'
                    '  touch "$TEST_PUSH_MARKER"\n'
                    '  exit 0\n'
                    'fi\n'
                    'exit 97\n',
                    encoding="utf-8",
                )
                fake_kaggle.chmod(0o755)
                env = os.environ.copy()
                env.update({
                    "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
                    "RUN_DIR": str(run_dir),
                    "KAGGLE_USERNAME": "offline-test",
                    "KAGGLE_KERNEL_SLUG": "offline-test",
                    "TEST_KERNEL_STATUS": status,
                    "TEST_PUSH_MARKER": str(push_marker),
                })
                result = subprocess.run(
                    ["bash", "-c", script], cwd=ROOT, env=env,
                    capture_output=True, text=True, timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    (run_dir / "status.txt").read_text(encoding="utf-8").strip(),
                    "KAGGLE_RETRY_REQUIRES_REVIEW",
                )
                self.assertFalse(push_marker.exists(), result.stdout)
                self.assertFalse((run_dir / "kaggle_push.log").exists())


    def test_combined_inference_hold_and_terminal_failure_guards(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("steps.reuse_guard.outputs.hold != 'true'"), 4)
        self.assertIn('cron: "17 1 * * *"', workflow)
        self.assertIn("group: daily-gpt2-training-canonical-kernel", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("KAGGLE_RETRY_REQUIRES_REVIEW", workflow)



if __name__ == "__main__":
    unittest.main()
