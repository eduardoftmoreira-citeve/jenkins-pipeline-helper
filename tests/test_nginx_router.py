from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda handle: {}))

from deploylib.config import NginxSettings
from deploylib.environment import resolve_environment
from deploylib.router import NginxRouter


class FakeDocker:
    def __init__(self, nginx_test_returncode: int = 0) -> None:
        self.connected = []
        self.checked = []
        self.executed = []
        self.nginx_test_returncode = nginx_test_returncode

    def connect_network(self, network: str, container: str) -> None:
        self.connected.append((network, container))

    def assert_connected_to_network(self, network: str, container: str) -> None:
        self.checked.append((network, container))

    def exec(self, container, command, check=True):
        self.executed.append((container, list(command), check))
        if list(command) == ["nginx", "-t"]:
            return type("Result", (), {"returncode": self.nginx_test_returncode, "stdout": "", "stderr": "bad config"})()
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()


class NginxRouterTests(unittest.TestCase):
    def test_route_uses_runtime_docker_resolution_and_strips_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            docker = FakeDocker()
            router = NginxRouter(
                docker,
                NginxSettings(
                    enabled=True,
                    container="nginx-proxy",
                    locations_dir=temp_dir,
                    route_prefix="piloto-cicd",
                ),
            )
            env = resolve_environment("staging")
            path = router.deploy(
                project="pps7-api",
                environment=env,
                service="api",
                container="cicd-pps7-api-api-staging",
                port=3000,
                network="cicd-pps7-api-staging",
            )
            self.assertEqual(path, "/piloto-cicd/pps7-api/staging/api/")
            config_file = Path(temp_dir) / "piloto-cicd-pps7-api-staging-api.conf"
            rendered = config_file.read_text(encoding="utf-8")
            self.assertIn("proxy_pass http://cicd-pps7-api-api-staging:3000/;", rendered)
            self.assertIn("proxy_set_header X-Forwarded-Prefix /piloto-cicd/pps7-api/staging/api;", rendered)
            self.assertEqual(docker.connected, [("cicd-pps7-api-staging", "nginx-proxy")])
            self.assertEqual(docker.checked, [])

    def test_public_url_uses_configured_reverse_proxy_base(self):
        router = NginxRouter(
            FakeDocker(),
            NginxSettings(public_url="https://dev.citeve.pt"),
        )
        self.assertEqual(
            router.public_url("/piloto-cicd/pps7-api/staging/api/"),
            "https://dev.citeve.pt/piloto-cicd/pps7-api/staging/api/",
        )

    def test_rejected_new_route_is_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            router = NginxRouter(
                FakeDocker(nginx_test_returncode=1),
                NginxSettings(
                    enabled=True,
                    container="nginx-proxy",
                    locations_dir=temp_dir,
                    route_prefix="piloto-cicd",
                ),
            )

            with self.assertRaisesRegex(RuntimeError, "Nginx rejected"):
                router.deploy(
                    project="pps7-api",
                    environment=resolve_environment("staging"),
                    service="api",
                    container="cicd-pps7-api-api-staging",
                    port=3000,
                    network="cicd-pps7-api-staging",
                )

            self.assertFalse((Path(temp_dir) / "piloto-cicd-pps7-api-staging-api.conf").exists())

    def test_rejected_route_update_restores_previous_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "piloto-cicd-pps7-api-staging-api.conf"
            config_file.write_text("previous config\n", encoding="utf-8")
            router = NginxRouter(
                FakeDocker(nginx_test_returncode=1),
                NginxSettings(
                    enabled=True,
                    container="nginx-proxy",
                    locations_dir=temp_dir,
                    route_prefix="piloto-cicd",
                ),
            )

            with self.assertRaisesRegex(RuntimeError, "Nginx rejected"):
                router.deploy(
                    project="pps7-api",
                    environment=resolve_environment("staging"),
                    service="api",
                    container="cicd-pps7-api-api-staging",
                    port=3000,
                    network="cicd-pps7-api-staging",
                )

            self.assertEqual(config_file.read_text(encoding="utf-8"), "previous config\n")


if __name__ == "__main__":
    unittest.main()
