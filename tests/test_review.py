from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deploylib.config import load_platform_config
from deploylib.review import (
    DiffSnapshot,
    GitHubClient,
    ReviewError,
    build_review_prompt,
    parse_repository_coordinates,
)


class ReviewTests(unittest.TestCase):
    def test_committed_platform_config_enables_review(self):
        repository = Path(__file__).resolve().parents[1]
        settings = load_platform_config(repository / "resources" / "platform-config.yaml").review
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

    def test_github_client_updates_existing_marked_comment(self):
        repository = Path(__file__).resolve().parents[1]
        settings = load_platform_config(repository / "resources" / "platform-config.yaml").review
        client = GitHubClient(settings, "not-a-real-token")
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

    def test_github_token_is_required(self):
        repository = Path(__file__).resolve().parents[1]
        settings = load_platform_config(repository / "resources" / "platform-config.yaml").review
        with self.assertRaises(ReviewError):
            GitHubClient(settings, "")


if __name__ == "__main__":
    unittest.main()
