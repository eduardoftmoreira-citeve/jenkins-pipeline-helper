from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "resources" / "python"))
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda handle: {}))
sys.modules.setdefault("fcntl", types.SimpleNamespace(LOCK_EX=2, LOCK_UN=8, flock=lambda handle, flag: None))

from deploy import print_deploy_summary
from deploylib.config import NginxSettings
from deploylib.router import NginxRouter
from deploylib.model import ProjectSpec


class DeploySummaryTests(unittest.TestCase):
    def test_summary_prints_live_url_and_runtime_details(self):
        engine = type(
            "Engine",
            (),
            {"router": NginxRouter(docker=None, settings=NginxSettings(public_url="https://dev.citeve.pt"))},
        )()
        state = {
            "environment": {"branch": "staging", "name": "staging", "kind": "staging"},
            "network": "cicd-pps7-api-staging",
            "resources": {
                "redis": {
                    "name": "redis",
                    "type": "redis",
                    "container": "cicd-pps7-api-redis-staging",
                    "image": "redis:7",
                }
            },
            "services": {
                "api": {
                    "name": "api",
                    "type": "node",
                    "container": "cicd-pps7-api-api-staging",
                    "image": "cicd/pps7-api-api:staging-43",
                    "route": "/piloto-cicd/pps7-api/staging/api/",
                }
            },
        }

        output = StringIO()
        with redirect_stdout(output):
            print_deploy_summary(ProjectSpec("pps7-api", [], []), state, engine)

        summary = output.getvalue()
        self.assertIn("=== Deployment summary ===", summary)
        self.assertIn("Project: pps7-api", summary)
        self.assertIn("Network: cicd-pps7-api-staging", summary)
        self.assertIn("cicd-pps7-api-api-staging", summary)
        self.assertIn("App live at: https://dev.citeve.pt/piloto-cicd/pps7-api/staging/api/", summary)


if __name__ == "__main__":
    unittest.main()
