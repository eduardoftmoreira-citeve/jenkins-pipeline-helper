from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from deploylib.config import load_platform_config
from deploylib.review import (
    DiffSnapshot,
    GitHubClient,
    OllamaClient,
    OpenPullRequest,
    ReviewError,
    build_review_prompt,
    parse_repository_coordinates,
    review_open_pull_request,
)


class ReviewTests(unittest.TestCase):
    @property
    def settings(self):
        repository = Path(__file__).resolve().parents[1]
        return load_platform_config(repository / "resources" / "platform-config.yaml").review

    def test_committed_platform_config_enables_review(self):
        settings = self.settings
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.ollama_model, "qwen2.5-coder:7b")
        self.assertTrue(settings.ollama_generate_url.endswith("/api/generate"))

    def test_remote_coordinates_support_https_and_ssh(self):
        self.assertEqual(
            parse_repository_coordinates("https://github.com/example/research-api.git"),
            ("example", "research-api"),
        )
        self.assertEqual(
            parse_repository_coordinates("git@github.com:example/research-api.git"),
            ("example", "research-api"),
        )

    def test_prompt_marks_diff_as_untrusted_and_reports_bounds(self):
        snapshot = DiffSnapshot(
            base_commit="base", head_commit="head", files=("api.py",),
            omitted_files=2, text="diff --git a/api.py b/api.py", truncated=True,
        )
        prompt = build_review_prompt(snapshot)
        self.assertIn("<untrusted_diff>", prompt)
        self.assertIn("Omitted files", prompt)
        self.assertIn("truncated", prompt.lower())

    def test_github_client_finds_one_open_pr_for_branch(self):
        client = GitHubClient(self.settings, "not-a-real-token")
        calls = []

        def fake_request(method, path, payload=None):
            calls.append((method, path, payload))
            return [{
                "number": 42,
                "html_url": "https://github.com/example/repo/pull/42",
                "head": {"ref": "feature/login"},
                "base": {"ref": "develop"},
            }]

        with patch.object(client, "_request_json", side_effect=fake_request):
            pull = client.find_open_pull_request("example", "repo", "refs/heads/feature/login")
        self.assertIsNotNone(pull)
        self.assertEqual(pull.number, "42")
        self.assertEqual(pull.base_branch, "develop")
        self.assertIn("head=example%3Afeature%2Flogin", calls[0][1])

    def test_github_client_returns_none_when_branch_has_no_open_pr(self):
        client = GitHubClient(self.settings, "not-a-real-token")
        with patch.object(client, "_request_json", return_value=[]):
            self.assertIsNone(client.find_open_pull_request("example", "repo", "feature/login"))

    def test_github_client_rejects_ambiguous_open_prs(self):
        client = GitHubClient(self.settings, "not-a-real-token")
        pulls = [
            {"number": 7, "head": {"ref": "feature/login"}, "base": {"ref": "develop"}},
            {"number": 8, "head": {"ref": "feature/login"}, "base": {"ref": "staging"}},
        ]
        with patch.object(client, "_request_json", return_value=pulls):
            with self.assertRaisesRegex(ReviewError, "Found 2 open pull requests"):
                client.find_open_pull_request("example", "repo", "feature/login")

    def test_github_client_updates_existing_marked_comment(self):
        client = GitHubClient(self.settings, "not-a-real-token")
        calls = []

        def fake_request(method, path, payload=None):
            calls.append((method, path, payload))
            if method == "GET":
                return [{"id": 44, "body": "<!-- cicd-ollama-review -->\nold"}]
            return {"html_url": "https://github.com/example/repo/pull/7#issuecomment-44"}

        with patch.object(client, "_request_json", side_effect=fake_request):
            action, url = client.upsert_pull_request_comment("example", "repo", "7", "new")
        self.assertEqual(action, "updated")
        self.assertIn("issuecomment-44", url)
        self.assertEqual(calls[1][0], "PATCH")

    def test_no_open_pr_skips_before_ollama_or_git_diff(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"GITHUB_TOKEN": "token"}, clear=False):
            with patch.object(GitHubClient, "find_open_pull_request", return_value=None), \
                 patch.object(OllamaClient, "generate") as generate, \
                 patch("deploylib.review.collect_pull_request_diff") as collect:
                result = review_open_pull_request(
                    settings=self.settings,
                    workspace=Path(temp),
                    repo_url="https://github.com/example/repo.git",
                    branch="feature/login",
                )
        self.assertEqual(result.status, "skipped")
        self.assertIn("No open", result.message)
        generate.assert_not_called()
        collect.assert_not_called()

    def test_github_token_is_required_for_branch_lookup(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            result = review_open_pull_request(
                settings=self.settings,
                workspace=Path(temp),
                repo_url="https://github.com/example/repo.git",
                branch="feature/login",
            )
        self.assertEqual(result.status, "skipped")
        self.assertIn("GITHUB_TOKEN", result.message)


if __name__ == "__main__":
    unittest.main()
