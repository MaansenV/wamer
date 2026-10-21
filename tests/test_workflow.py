"""Regression contracts for the real GitHub workflow and embedded shell steps."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/warm.yml"


def job(text, name):
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  [\w-]+:|\Z)", text, re.M | re.S)
    return match.group(1)


def step(text, name):
    match = re.search(rf"^      - name: {re.escape(name)}\n(.*?)(?=^      - |\Z)", text, re.M | re.S)
    return match.group(1) if match else ""


def script(block):
    return "\n".join(line[10:] for line in block.split("        run: |\n", 1)[1].splitlines()
                     if line.startswith("          "))


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_overlapping_runs_cannot_rotate_the_same_tokens(self):
        self.assertTrue(re.search(r"(?m)^concurrency:\n  group: .+\n  cancel-in-progress: false$", self.text))

    def test_failed_state_push_is_not_reported_as_success(self):
        bash = (str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
                if os.name == "nt" else shutil.which("bash"))
        if not bash or not Path(bash).exists():
            self.skipTest("Bash is unavailable")
        for provider in ("warm-claude",):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as cwd:
                code = script(step(job(self.text, provider), "Record warm timestamp"))
                result = subprocess.run(
                    [bash, "-e", "-c", 'git() { case "$1" in diff|push) return 1;; esac; }; '
                     'sleep() { :; }; export -f git sleep;\n' + code],
                    cwd=cwd, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Failed to record", result.stdout)


if __name__ == "__main__":
    unittest.main()
