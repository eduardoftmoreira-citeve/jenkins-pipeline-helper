from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from deploylib.config import load_application_config, load_platform_config
from deploylib.model import ProjectSpec


class ConfigTests(unittest.TestCase):
    def test_single_app_config_is_loaded_for_every_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "app-config.yaml").write_text(
                "project_name: demo\nservices:\n  api:\n    type: node\n    port: 3000\n    env:\n      NODE_ENV: development\n",
                encoding="utf-8",
            )
            raw = load_application_config(workspace)
            project = ProjectSpec.from_dict(raw)
            self.assertEqual(project.name, "demo")
            self.assertEqual(project.services[0].env["NODE_ENV"], "development")

    def test_base_path_is_opt_in(self):
        project = ProjectSpec.from_dict({
            "project_name": "demo",
            "services": {
                "api": {
                    "type": "node",
                    "port": 3000,
                    "route": {"enabled": True, "inject_base_path": True},
                }
            },
        })
        self.assertTrue(project.services[0].route_enabled)
        self.assertTrue(project.services[0].inject_base_path)

    def test_base_path_requires_route(self):
        with self.assertRaises(ValueError):
            ProjectSpec.from_dict({
                "project_name": "demo",
                "services": {
                    "api": {
                        "type": "node",
                        "port": 3000,
                        "route": {"enabled": False, "inject_base_path": True},
                    }
                },
            })

    def test_service_cannot_reference_unknown_infrastructure(self):
        with self.assertRaises(ValueError):
            ProjectSpec.from_dict({
                "project_name": "demo",
                "services": {"api": {"type": "node", "port": 3000, "depends_on": ["missing"]}},
            })

    def test_committed_platform_config_loads(self):
        repository = Path(__file__).resolve().parents[1]
        platform = load_platform_config(repository / "resources" / "platform-config.yaml")
        self.assertEqual(platform.nginx.locations_dir, "/home/users/cgomes/nginx/locations")
        self.assertTrue(platform.backup_settings_for("mongo").policies["production"].verify_restore)

    def test_infrastructure_auth_is_not_supported(self):
        with self.assertRaisesRegex(ValueError, "without authentication"):
            ProjectSpec.from_dict({
                "project_name": "demo",
                "infrastructure": {"mongo": {"type": "mongo", "auth": {"enabled": True}}},
                "services": {"api": {"type": "node", "port": 3000}},
            })

    def test_platform_reads_backup_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "platform-config.yaml"
            config_path.write_text(
                "state_dir: /tmp/state\n"
                "backups:\n  providers:\n    mongo:\n      root_dir: /tmp/backups\n      policies:\n        production:\n"
                "          enabled: true\n          daily_retention_days: 14\n          weekly_retention_weeks: 8\n"
                "          monthly_retention_months: 12\n          verify_restore: true\n",
                encoding="utf-8",
            )
            platform = load_platform_config(config_path)
            production = platform.backup_settings_for("mongo").policies["production"]
            self.assertTrue(production.enabled)
            self.assertTrue(production.verify_restore)
            self.assertEqual(production.monthly_retention_months, 12)


if __name__ == "__main__":
    unittest.main()
