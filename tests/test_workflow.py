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
        cls.codex = job(cls.text, "warm-codex")

    def persist_step(self):
        return step(self.codex, "Persist refreshed auth back to secret") or step(
            self.codex, "Persist refreshed auth back to secret (best-effort)")

    def test_writeback_error_is_not_ignored(self):
        self.assertNotIn("continue-on-error: true", self.persist_step())

    def test_writeback_runs_after_failed_send_too(self):
        block = self.persist_step()
        self.assertIn("always()", block)
        self.assertIn("steps.warm.outcome != 'skipped'", block)
        self.assertNotIn("env.GH_PAT != ''", block)

    def test_pat_preflight_is_required_before_sending(self):
        block = step(self.codex, "Validate secret write-back access")
        self.assertIn("gh api", block)
        self.assertIn("actions/secrets/public-key", block)
        self.assertIn("gh secret set CODEX_AUTH_JSON", block)
        self.assertLess(self.codex.index("Validate secret write-back access"),
                        self.codex.index("Send warm-up prompt"))

    def test_skip_does_not_close_failure_issue(self):
        block = step(job(self.text, "notify"), "Close resolved failure issue")
        self.assertIn("needs.warm-claude.outputs.warmed == 'true'", block)
        self.assertIn("needs.warm-codex.outputs.warmed == 'true'", block)

    def test_overlapping_runs_cannot_rotate_the_same_tokens(self):
        self.assertTrue(re.search(r"(?m)^concurrency:\n  group: .+\n  cancel-in-progress: false$", self.text))

    def test_gh_token_failure_reaches_shell_exit(self):
        bash = (str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
                if os.name == "nt" else shutil.which("bash"))
        if not bash or not Path(bash).exists():
            self.skipTest("Bash is unavailable")
        with tempfile.TemporaryDirectory() as home:
            auth_dir = Path(home) / ".codex"
            auth_dir.mkdir()
            (auth_dir / "auth.json").write_text(
                '{"tokens": {"access_token": "fixture-access", "refresh_token": "fixture-refresh"}}')
            marker = Path(home) / "gh-called"
            code = re.sub(r"\$\{\{.*?\}\}", "fixture/repo", script(self.persist_step()))
            result = subprocess.run(
                [bash, "-e", "-c", 'gh() { echo called >> "$GH_MARKER"; return 1; }; '
                 'sleep() { :; }; python3() { "$PYTHON_EXE" "$@"; }; '
                 'export -f gh sleep python3;\n' + code],
                cwd=ROOT, env={**os.environ, "HOME": home, "GH_TOKEN": "fixture",
                               "GH_MARKER": str(marker), "PYTHON_EXE": sys.executable},
                capture_output=True, text=True, timeout=10)
            self.assertTrue(marker.exists(), result.stderr)
            self.assertNotEqual(result.returncode, 0)

    def test_failed_state_push_is_not_reported_as_success(self):
        bash = (str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
                if os.name == "nt" else shutil.which("bash"))
        if not bash or not Path(bash).exists():
            self.skipTest("Bash is unavailable")
        for provider in ("warm-claude", "warm-codex"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as cwd:
                code = script(step(job(self.text, provider), "Record warm timestamp"))
                result = subprocess.run(
                    [bash, "-e", "-c", 'git() { case "$1" in diff|push) return 1;; esac; }; '
                     'sleep() { :; }; export -f git sleep;\n' + code],
                    cwd=cwd, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Failed to record", result.stdout)

    def test_pat_is_scoped_to_preflight_and_writeback(self):
        self.assertNotIn("      GH_PAT:", self.codex)
        self.assertEqual(self.codex.count("GH_TOKEN: ${{ secrets.GH_PAT }}"), 2)

    def test_record_real_send_even_if_writeback_failed(self):
        block = step(self.codex, "Record warm timestamp")
        self.assertIn("always() && steps.warm.outcome == 'success'", block)
        self.assertIn("exit 1", script(block))


class MaskAuthTests(unittest.TestCase):
    def run_mask(self, contents):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "auth.json"
            path.write_text(contents, encoding="utf-8")
            return subprocess.run([sys.executable, str(ROOT / "scripts/mask_codex_auth.py"), str(path)],
                                  capture_output=True, text=True, timeout=10)

    def test_all_token_fields_are_masked_and_escaped(self):
        result = self.run_mask('{"tokens":{"access_token":"new-access",'
                               '"refresh_token":"new%refresh\\nline", "id_token":"new-id",'
                               '"account_id":"account"}}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("::add-mask::new-access", result.stdout)
        self.assertIn("::add-mask::new%25refresh%0Aline", result.stdout)
        self.assertIn("::add-mask::new-id", result.stdout)

    def test_invalid_auth_does_not_echo_the_payload(self):
        result = self.run_mask('{"tokens": "do-not-leak-this"}')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("do-not-leak-this", result.stdout + result.stderr)

    def test_api_key_is_not_accepted_instead_of_subscription_auth(self):
        result = self.run_mask('{"OPENAI_API_KEY":"fixture-api-key"}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("::add-mask::fixture-api-key", result.stdout)


if __name__ == "__main__":
    unittest.main()
