from pathlib import Path
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda handle: {}))

from deploylib.review import _run_git, collect_pull_request_diff


def git(args, *, cwd=None):
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout


class ReviewDiffTests(unittest.TestCase):
    def test_collects_target_to_head_diff_with_file_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote.git"
            work = root / "work"
            git(["init", "--bare", "--initial-branch=main", str(remote)])
            git(["clone", str(remote), str(work)])
            git(["config", "user.email", "ci@example.test"], cwd=work)
            git(["config", "user.name", "CI Test"], cwd=work)
            (work / "base.txt").write_text("base\n", encoding="utf-8")
            git(["add", "base.txt"], cwd=work)
            git(["commit", "-m", "base"], cwd=work)
            git(["push", "origin", "main"], cwd=work)
            git(["checkout", "-b", "feature/review"], cwd=work)
            (work / "one.py").write_text("print('one')\n", encoding="utf-8")
            (work / "two.py").write_text("print('two')\n", encoding="utf-8")
            git(["add", "one.py", "two.py"], cwd=work)
            git(["commit", "-m", "feature"], cwd=work)

            snapshot = collect_pull_request_diff(work, "main", max_files=1, max_characters=10_000)
            self.assertEqual(len(snapshot.files), 1)
            self.assertEqual(snapshot.omitted_files, 1)
            self.assertIn("diff --git", snapshot.text)
            self.assertFalse(snapshot.truncated)

    def test_authenticated_git_uses_askpass_environment(self):
        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            captured["env"] = kwargs.get("env")
            return type("Result", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})()

        with tempfile.TemporaryDirectory() as temp, \
             patch.dict(os.environ, {"GITHUB_TOKEN": "secret-token", "GITHUB_USERNAME": "x-access-token"}, clear=False), \
             patch("subprocess.run", side_effect=fake_run):
            output = _run_git(Path(temp), ["fetch", "--no-tags", "origin", "refs/heads/main"], authenticated=True)

        self.assertEqual(output, "ok\n")
        self.assertEqual(captured["args"][:2], ["git", "fetch"])
        self.assertEqual(captured["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(captured["env"]["GIT_USERNAME"], "x-access-token")
        self.assertEqual(captured["env"]["GIT_PASSWORD"], "secret-token")
        self.assertIn("GIT_ASKPASS", captured["env"])


if __name__ == "__main__":
    unittest.main()
