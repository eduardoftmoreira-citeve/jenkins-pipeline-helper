from __future__ import annotations

import unittest

from deploylib.environment import UnsupportedBranch, resolve_environment


class EnvironmentTests(unittest.TestCase):
    def test_static_branches(self):
        self.assertEqual(resolve_environment("main").name, "prod")
        self.assertFalse(resolve_environment("main").shared_mongo)
        self.assertEqual(resolve_environment("develop").name, "dev")
        self.assertTrue(resolve_environment("develop").shared_mongo)
        self.assertEqual(resolve_environment("staging").name, "staging")

    def test_static_branch_aliases(self):
        for branch in ("main", "master", "prod", "production", "refs/heads/master"):
            with self.subTest(branch=branch):
                environment = resolve_environment(branch)
                self.assertEqual(environment.name, "prod")
                self.assertEqual(environment.kind, "production")
                self.assertFalse(environment.shared_mongo)
                self.assertFalse(environment.ephemeral)

        for branch in ("stage", "staging", "origin/stage"):
            with self.subTest(branch=branch):
                environment = resolve_environment(branch)
                self.assertEqual(environment.name, "staging")
                self.assertEqual(environment.kind, "staging")
                self.assertTrue(environment.shared_mongo)
                self.assertFalse(environment.ephemeral)

        for branch in ("dev", "develop", "development", "refs/heads/development"):
            with self.subTest(branch=branch):
                environment = resolve_environment(branch)
                self.assertEqual(environment.name, "dev")
                self.assertEqual(environment.kind, "development")
                self.assertTrue(environment.shared_mongo)
                self.assertFalse(environment.ephemeral)

    def test_feature_branch_keeps_full_identity(self):
        environment = resolve_environment("feature/payments/api")
        self.assertEqual(environment.branch, "feature/payments/api")
        self.assertRegex(environment.name, r"^feature-payments-api-[0-9a-f]{6}$")
        self.assertTrue(environment.ephemeral)
        self.assertTrue(environment.shared_mongo)

    def test_bugfix_branch_is_ephemeral(self):
        environment = resolve_environment("bugfix/redis-timeout")
        self.assertRegex(environment.name, r"^bugfix-redis-timeout-[0-9a-f]{6}$")
        self.assertTrue(environment.ephemeral)

    def test_unknown_branch_is_rejected(self):
        with self.assertRaises(UnsupportedBranch):
            resolve_environment("release/1.0")


if __name__ == "__main__":
    unittest.main()
