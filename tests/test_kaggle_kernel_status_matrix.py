"""Offline matrix tests for the real Kaggle Bash step. No network or GPU."""
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def launch_script():
    lines = (ROOT / ".github/workflows/daily-gpt2-training.yml").read_text(
        encoding="utf-8"
    ).splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.strip() == "- name: Launch, monitor, and download")
    begin = next(i for i in range(start + 1, len(lines))
                 if lines[i].strip() == "run: |")
    end = next(i for i in range(begin + 1, len(lines))
               if lines[i].startswith("      - name: "))
    return textwrap.dedent("\n".join(lines[begin + 1:end])) + "\n"


FAKE_KAGGLE = r'''#!/usr/bin/env python3
import os
import sys
from pathlib import Path
run = Path(os.environ["RUN_DIR"])
command = sys.argv[2] if len(sys.argv) > 2 else ""
scenario = os.environ["FAKE_SCENARIO"]
count_file = run / "fake_status_calls.txt"
if command == "status":
    count = int(count_file.read_text()) if count_file.exists() else 0
    count_file.write_text(str(count + 1))
    if count > 0:
        print("KernelWorkerStatus.COMPLETE")
    elif scenario == "running":
        print("KernelWorkerStatus.RUNNING")
    elif scenario == "queued":
        print("KernelWorkerStatus.QUEUED")
    elif scenario == "failed":
        print("KernelWorkerStatus.FAILED")
    elif scenario == "complete":
        print("KernelWorkerStatus.COMPLETE")
    elif scenario == "missing":
        print("404 No such kernel")
        sys.exit(1)
    elif scenario == "unauthorized":
        print("403 Unauthorized")
        sys.exit(1)
    else:
        print("Unrecognized remote state")
elif command == "push":
    (run / "fake_push.txt").write_text("submitted")
elif command == "output":
    output_dir = Path(sys.argv[sys.argv.index("-p") + 1])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "fake_result.txt").write_text("fixture only")
else:
    sys.exit(2)
'''


class KaggleKernelStatusMatrixTests(unittest.TestCase):
    def simulate(self, scenario, approve_failed=False):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            run.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            kaggle = bin_dir / "kaggle"
            kaggle.write_text(FAKE_KAGGLE, encoding="utf-8")
            kaggle.chmod(0o755)
            sleep = bin_dir / "sleep"
            sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            sleep.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "RUN_DIR": str(run), "FAKE_SCENARIO": scenario,
                "KAGGLE_USERNAME": "fixture", "KAGGLE_KERNEL_SLUG": "fixture-kernel",
                "APPROVE_FAILED_KERNEL_RETRY": "true" if approve_failed else "false",
                "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
            })
            proc = subprocess.run(
                ["bash", "-c", launch_script()], cwd=ROOT, env=env,
                capture_output=True, text=True, timeout=15
            )
            status_file = run / "status.txt"
            status = status_file.read_text().strip() if status_file.exists() else "MISSING"
            return (proc.returncode, status, (run / "fake_push.txt").exists(),
                    (run / "kaggle_output" / "fake_result.txt").exists(), proc.stdout)

    def test_running_and_queued_not_resubmitted_or_misattributed(self):
        for state in ("running", "queued"):
            with self.subTest(state=state):
                code, status, pushed, downloaded, _ = self.simulate(state)
                self.assertEqual((code, status, pushed, downloaded),
                                 (0, "BLOCKED_EXISTING_KERNEL_ACTIVE", False, False))

    def test_failed_requires_review(self):
        code, status, pushed, downloaded, _ = self.simulate("failed")
        self.assertEqual((code, status, pushed, downloaded),
                         (0, "BLOCKED_FAILED_KERNEL_REQUIRES_APPROVAL", False, False))

    def test_failed_approved_allows_one_submission(self):
        code, status, pushed, downloaded, _ = self.simulate("failed", approve_failed=True)
        self.assertEqual((code, status, pushed, downloaded), (0, "COMPLETE", True, True))

    def test_unknown_or_unauthorized_refuses_submission(self):
        for state in ("unknown", "unauthorized"):
            with self.subTest(state=state):
                code, status, pushed, downloaded, _ = self.simulate(state)
                self.assertEqual((code, status, pushed, downloaded),
                                 (0, "KAGGLE_STATUS_FAILED", False, False))

    def test_complete_or_missing_enters_upstream_approved_path(self):
        # Upstream same-data guard is tested separately; this is only the
        # downstream state branch and its single mock submission.
        for state in ("complete", "missing"):
            with self.subTest(state=state):
                code, status, pushed, downloaded, _ = self.simulate(state)
                self.assertEqual((code, status, pushed, downloaded),
                                 (0, "COMPLETE", True, True))


if __name__ == "__main__":
    unittest.main()
