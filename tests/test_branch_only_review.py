from pathlib import Path
import unittest


class BranchOnlyReviewConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.repository = Path(__file__).resolve().parents[1]

    def test_job_dsl_discovers_branches_but_not_pr_jobs(self):
        dsl = (self.repository / "dsl" / "jobs.groovy").read_text(encoding="utf-8")
        self.assertIn("gitHubBranchDiscovery", dsl)
        self.assertIn("headRegexFilter", dsl)
        self.assertIn("main|master|prod|production", dsl)
        self.assertIn("stage|staging", dsl)
        self.assertIn("dev|develop|development", dsl)
        self.assertIn("release/.+", dsl)
        self.assertIn("bugfix/.+", dsl)
        self.assertNotIn("feature/.+", dsl)
        self.assertNotIn("gitHubPullRequestDiscovery", dsl)

    def test_review_step_uses_branch_and_fixed_checkout_credential(self):
        groovy = (self.repository / "vars" / "reviewPullRequest.groovy").read_text(encoding="utf-8")
        self.assertIn("env.BRANCH_NAME", groovy)
        self.assertIn("credentialsId: 'github-PAT'", groovy)
        self.assertIn("--branch", groovy)
        self.assertNotIn("CHANGE_ID", groovy)
        self.assertNotIn("CHANGE_TARGET", groovy)
        self.assertNotIn("githubTokenCredentialId", groovy)

    def test_cleanup_binds_github_token_for_private_ls_remote(self):
        groovy = (self.repository / "vars" / "cleanupOrphans.groovy").read_text(encoding="utf-8")
        self.assertIn("withCredentials", groovy)
        self.assertIn("credentialsId: 'github-PAT'", groovy)
        self.assertIn("passwordVariable: 'GITHUB_TOKEN'", groovy)
        self.assertIn("--repo-url", groovy)


if __name__ == "__main__":
    unittest.main()
