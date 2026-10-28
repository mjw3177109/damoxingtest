"""Execute the terminal-failure Kaggle shell branch with a fake CLI.

This is a zero-network, zero-GPU regression test: a terminal failure must
never call `kaggle kernels push`, even when the shell step itself exits 0.
"""
import os
import subprocess
import sys
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


    def test_unknown_or_unauthorized_status_cannot_push(self):
        """Unrecognized status or CLI/auth failure must not spend GPU."""
        script = launch_shell_script()
        for status, exit_code in (
            ("unexpected kernel response", 0),
            ("403 Forbidden", 1),
            ("API rate limit exceeded", 1),
            ("403 Forbidden: user not found (404)", 1),
            ("429 API rate limit exceeded: kernel not found", 1),
            # Some wrappers can exit 0 and mix COMPLETE with API errors.
            # The initial status check must fail closed before any GPU push.
            ("KernelWorkerStatus.COMPLETE\\n403 Forbidden", 0),
            ("Status: COMPLETE\\n429 Too Many Requests", 0),
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
                    '  exit "$TEST_KERNEL_EXIT_CODE"\n'
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
                    "TEST_KERNEL_EXIT_CODE": str(exit_code),
                    "TEST_PUSH_MARKER": str(push_marker),
                })
                result = subprocess.run(
                    ["bash", "-c", script], cwd=ROOT, env=env,
                    capture_output=True, text=True, timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    (run_dir / "status.txt").read_text(encoding="utf-8").strip(),
                    "KAGGLE_STATUS_FAILED",
                )
                self.assertFalse(push_marker.exists(), result.stdout)
                self.assertFalse((run_dir / "kaggle_push.log").exists())


    def test_existing_active_kernel_is_monitored_without_duplicate_push(self):
        """A RUNNING/QUEUED/PENDING remote kernel must never be resubmitted."""
        script = launch_shell_script()
        for active_status in (
            "KernelWorkerStatus.RUNNING",
            "Status: QUEUED",
            "KernelWorkerStatus.PENDING",
        ):
            with self.subTest(active_status=active_status), tempfile.TemporaryDirectory() as tmp:
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
                    '  if [[ ! -f "$TEST_STATUS_MARKER" ]]; then\n'
                    '    touch "$TEST_STATUS_MARKER"\n'
                    '    printf "%s\\n" "$TEST_ACTIVE_STATUS"\n'
                    '  else\n'
                    '    printf "KernelWorkerStatus.COMPLETE\\n"\n'
                    '  fi\n'
                    '  exit 0\n'
                    'fi\n'
                    'if [[ "$1" == "kernels" && "$2" == "push" ]]; then\n'
                    '  touch "$TEST_PUSH_MARKER"\n'
                    '  exit 0\n'
                    'fi\n'
                    'if [[ "$1" == "kernels" && "$2" == "output" ]]; then\n'
                    '  mkdir -p "$RUN_DIR/kaggle_output"\n'
                    '  printf "offline existing kernel result\\n" > "$RUN_DIR/kaggle_output/marker.txt"\n'
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
                    "TEST_ACTIVE_STATUS": active_status,
                    "TEST_STATUS_MARKER": str(root / "status_seen"),
                    "TEST_PUSH_MARKER": str(push_marker),
                })
                result = subprocess.run(
                    ["bash", "-c", script], cwd=ROOT, env=env,
                    capture_output=True, text=True, timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    (run_dir / "status.txt").read_text(encoding="utf-8").strip(),
                    "COMPLETE",
                )
                self.assertTrue((run_dir / "kaggle_output/marker.txt").is_file())
                self.assertFalse(push_marker.exists(), result.stdout)
                self.assertFalse((run_dir / "kaggle_push.log").exists())


    def test_rate_limit_during_polling_stops_without_retry(self):
        """An active kernel followed by 429 must stop promptly, never push."""
        script = launch_shell_script()
        for poll_status, exit_code in (
            ("429 Too Many Requests", 1),
            ("API rate limit exceeded", 1),
            ("429 Too Many Requests", 0),
            ("KernelWorkerStatus.COMPLETE\n429 Too Many Requests", 0),
        ):
            with self.subTest(poll_status=poll_status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bin_dir = root / "bin"
                bin_dir.mkdir()
                run_dir = root / "run"
                run_dir.mkdir()
                push_marker = root / "unexpected_push"
                fake_kaggle = bin_dir / "kaggle"
                fake_kaggle.write_text(
                    r"""#!/usr/bin/env bash
if [[ "$1" == "kernels" && "$2" == "status" ]]; then
  if [[ ! -f "$TEST_STATUS_MARKER" ]]; then
    touch "$TEST_STATUS_MARKER"
    printf 'KernelWorkerStatus.RUNNING\n'
    exit 0
  fi
  printf '%s\n' "$TEST_POLL_STATUS"
  exit "$TEST_POLL_EXIT_CODE"
fi
if [[ "$1" == "kernels" && "$2" == "push" ]]; then
  touch "$TEST_PUSH_MARKER"
  exit 0
fi
exit 97
""",
                    encoding="utf-8",
                )
                fake_kaggle.chmod(0o755)
                env = os.environ.copy()
                env.update({
                    "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
                    "RUN_DIR": str(run_dir),
                    "KAGGLE_USERNAME": "offline-test",
                    "KAGGLE_KERNEL_SLUG": "offline-test",
                    "TEST_STATUS_MARKER": str(root / "status_seen"),
                    "TEST_POLL_STATUS": poll_status,
                    "TEST_POLL_EXIT_CODE": str(exit_code),
                    "TEST_PUSH_MARKER": str(push_marker),
                })
                result = subprocess.run(
                    ["bash", "-c", script], cwd=ROOT, env=env,
                    capture_output=True, text=True, timeout=8, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    (run_dir / "status.txt").read_text(encoding="utf-8").strip(),
                    "KAGGLE_STATUS_FAILED",
                )
                self.assertIn(poll_status, (run_dir / "kaggle_status.log").read_text(encoding="utf-8"))
                self.assertFalse(push_marker.exists(), result.stdout)
                self.assertFalse((run_dir / "kaggle_push.log").exists())


    def test_genuine_missing_kernel_is_pushed_once(self):
        """An unambiguous 404 permits one first creation, then monitors output."""
        script = launch_shell_script()
        for missing_status in ("404 Not Found: kernel does not exist", "No such kernel"):
            with self.subTest(missing_status=missing_status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bin_dir = root / "bin"
                bin_dir.mkdir()
                run_dir = root / "run"
                run_dir.mkdir()
                push_counter = root / "push_count"
                status_marker = root / "initial_status_seen"
                fake_kaggle = bin_dir / "kaggle"
                fake_kaggle.write_text(
                    '#!/usr/bin/env bash\n'
                    'if [[ "$1" == "kernels" && "$2" == "status" ]]; then\n'
                    '  if [[ ! -f "$TEST_STATUS_MARKER" ]]; then\n'
                    '    touch "$TEST_STATUS_MARKER"\n'
                    '    printf "%s\\n" "$TEST_MISSING_STATUS"\n'
                    '    exit 1\n'
                    '  fi\n'
                    '  printf "KernelWorkerStatus.COMPLETE\\n"\n'
                    '  exit 0\n'
                    'fi\n'
                    'if [[ "$1" == "kernels" && "$2" == "push" ]]; then\n'
                    '  printf "push\\n" >> "$TEST_PUSH_COUNTER"\n'
                    '  exit 0\n'
                    'fi\n'
                    'if [[ "$1" == "kernels" && "$2" == "output" ]]; then\n'
                    '  mkdir -p "$RUN_DIR/kaggle_output"\n'
                    '  printf "offline output only\\n" > "$RUN_DIR/kaggle_output/marker.txt"\n'
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
                    "TEST_MISSING_STATUS": missing_status,
                    "TEST_STATUS_MARKER": str(status_marker),
                    "TEST_PUSH_COUNTER": str(push_counter),
                })
                result = subprocess.run(
                    ["bash", "-c", script], cwd=ROOT, env=env,
                    capture_output=True, text=True, timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    (run_dir / "status.txt").read_text(encoding="utf-8").strip(),
                    "COMPLETE",
                )
                self.assertEqual(
                    push_counter.read_text(encoding="utf-8").splitlines(),
                    ["push"],
                )
                self.assertTrue((run_dir / "kaggle_output/marker.txt").is_file())


    def test_combined_inference_hold_and_terminal_failure_guards(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("steps.reuse_guard.outputs.hold != 'true'"), 4)
        self.assertIn('cron: "17 1 * * *"', workflow)
        self.assertIn("group: daily-gpt2-training-canonical-kernel", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("KAGGLE_RETRY_REQUIRES_REVIEW", workflow)



    def test_review_required_finalizes_as_blocked_without_fake_metrics(self):
        """The combined PR must never turn a refused retry into training success."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "status.txt").write_text(
                "KAGGLE_RETRY_REQUIRES_REVIEW\n", encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "finalize_report.py"),
                 "--run-dir", str(run_dir)],
                cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (run_dir / "final_status.txt").read_text(encoding="utf-8").strip(),
                "KAGGLE_RETRY_REQUIRES_REVIEW",
            )
            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("KAGGLE_RETRY_REQUIRES_REVIEW", report)
            self.assertNotIn("最终判定： **SUCCESS**", report)
            self.assertFalse((run_dir / "metrics.json").exists())
            self.assertFalse((run_dir / "samples.json").exists())


if __name__ == "__main__":
    unittest.main()
