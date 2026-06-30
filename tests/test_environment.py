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
