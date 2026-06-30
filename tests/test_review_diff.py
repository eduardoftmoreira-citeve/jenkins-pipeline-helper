from pathlib import Path
import subprocess
import tempfile
import unittest

from deploylib.review import collect_pull_request_diff


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


if __name__ == "__main__":
    unittest.main()
