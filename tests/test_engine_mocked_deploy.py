from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.modules.setdefault("fcntl", types.SimpleNamespace(LOCK_EX=2, LOCK_UN=8, flock=lambda handle, flag: None))
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda handle: {}))

from deploylib.command import CommandResult
from deploylib.config import NginxSettings, PlatformConfig
from deploylib.engine import DeploymentEngine
from deploylib.environment import resolve_environment
from deploylib.model import HealthCheck, InfrastructureSpec, ProjectSpec, ServiceSpec


class FakeDocker:
    def __init__(self, *, existing=None, running=None, health_statuses=None) -> None:
        self.calls = []
        self.runs = []
        self.builds = []
        self.existing = set(existing or [])
        self.running_map = dict(running or {})
        self.health_statuses = list(health_statuses or [])

    def ensure_network(self, name):
        self.calls.append(("ensure_network", name))

    def connect_network(self, network, container):
        self.calls.append(("connect_network", network, container))

    def container_exists(self, name):
        self.calls.append(("container_exists", name))
        return name in self.existing

    def run_container(self, **kwargs):
        self.calls.append(("run_container", kwargs["name"]))
        self.runs.append(kwargs)

    def build_image(self, image, dockerfile, context, build_args):
        self.calls.append(("build_image", image))
        self.builds.append((image, dockerfile, context, build_args))

    def exec(self, container, command, check=True, **_kwargs):
        self.calls.append(("exec", container, tuple(command), check))
        if command[:2] == ["redis-cli", "--raw"]:
            return CommandResult(0, "PONG\n", "")
        return CommandResult(0, "", "")

    def http_status(self, network, image, url):
        self.calls.append(("http_status", network, image, url))
        if self.health_statuses:
            return self.health_statuses.pop(0)
        return 200

    def running(self, name):
        self.calls.append(("running", name))
        return self.running_map.get(name, True)

    def restart_container(self, name):
        self.calls.append(("restart_container", name))
        self.running_map[name] = True

    def prune_dangling_images(self):
        self.calls.append(("prune_dangling_images",))


class EngineMockedDeployTests(unittest.TestCase):
    def test_deploy_orchestrates_infrastructure_service_route_and_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "Dockerfile").write_text("FROM node:22-alpine\n", encoding="utf-8")
            platform = PlatformConfig(
                state_dir=root / "state",
                network_prefix="cicd",
                image_namespace="cicd",
                curl_image="curlimages/curl",
                nginx=NginxSettings(
                    enabled=True,
                    container="nginx-proxy",
                    locations_dir=str(root / "nginx"),
                    route_prefix="piloto-cicd",
                    public_url="https://dev.citeve.pt",
                ),
                backups={},
            )
            docker = FakeDocker()
            logs = []
            engine = DeploymentEngine(platform, docker, reporter=logs.append)
            project = ProjectSpec(
                "pps7-api",
                [InfrastructureSpec("redis", "redis", "7", None)],
                [
                    ServiceSpec(
                        "api",
                        "node",
                        3000,
                        depends_on=["redis"],
                        health_check=HealthCheck(path="/health"),
                        route_enabled=True,
                    )
                ],
            )

            state = engine.deploy(project, resolve_environment("staging"), workspace, "43")

            self.assertEqual(state["network"], "cicd-pps7-api-staging")
            self.assertEqual(state["services"]["api"]["container"], "cicd-pps7-api-api-staging")
            self.assertEqual(state["services"]["api"]["route"], "/piloto-cicd/pps7-api/staging/api/")
            api_run = next(item for item in docker.runs if item["name"] == "cicd-pps7-api-api-staging")
            self.assertEqual(api_run["environment"]["REDIS_URL"], "redis://cicd-pps7-api-redis-staging:6379/0")
            self.assertIn(("ensure_network", "cicd-pps7-api-staging"), docker.calls)
            self.assertIn(("connect_network", "cicd-pps7-api-staging", "nginx-proxy"), docker.calls)
            self.assertIn(("build_image", "cicd/pps7-api-api:staging-43"), docker.calls)
            self.assertIn(("prune_dangling_images",), docker.calls)
            self.assertTrue(any("App is live at: https://dev.citeve.pt/piloto-cicd/pps7-api/staging/api/" in item for item in logs))

    def test_verify_restarts_stopped_service_and_checks_health(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            container = "cicd-pps7-api-api-staging"
            platform = PlatformConfig(
                state_dir=root / "state",
                network_prefix="cicd",
                image_namespace="cicd",
                curl_image="curlimages/curl",
                nginx=NginxSettings(),
                backups={},
            )
            docker = FakeDocker(existing={container}, running={container: False}, health_statuses=[200])
            engine = DeploymentEngine(platform, docker)
            project = ProjectSpec(
                "pps7-api",
                [],
                [ServiceSpec("api", "node", 3000, health_check=HealthCheck(path="/health"))],
            )
            state = engine._state_document(project, resolve_environment("staging"), "cicd-pps7-api-staging")
            state["services"] = {
                "api": {
                    "name": "api",
                    "type": "node",
                    "container": container,
                    "route": "/piloto-cicd/pps7-api/staging/api/",
                }
            }
            engine.state.save(project.name, "staging", state)

            results = engine.maintain(project, resolve_environment("staging"), operation="verify")

            self.assertEqual(results[0]["status"], "healthy")
            self.assertTrue(results[0]["restarted"])
            self.assertIn(("restart_container", container), docker.calls)
            self.assertIn(
                ("http_status", "cicd-pps7-api-staging", "curlimages/curl", f"http://{container}:3000/health"),
                docker.calls,
            )

    def test_verify_restarts_once_when_health_fails_then_recovers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            container = "cicd-pps7-api-api-staging"
            platform = PlatformConfig(
                state_dir=root / "state",
                network_prefix="cicd",
                image_namespace="cicd",
                curl_image="curlimages/curl",
                nginx=NginxSettings(),
                backups={},
            )
            docker = FakeDocker(existing={container}, running={container: True}, health_statuses=[500, 200])
            engine = DeploymentEngine(platform, docker)
            project = ProjectSpec(
                "pps7-api",
                [],
                [ServiceSpec("api", "node", 3000, health_check=HealthCheck(path="/health"))],
            )
            state = engine._state_document(project, resolve_environment("staging"), "cicd-pps7-api-staging")
            state["services"] = {"api": {"name": "api", "type": "node", "container": container}}
            engine.state.save(project.name, "staging", state)

            results = engine.maintain(project, resolve_environment("staging"), operation="verify")

            self.assertEqual(results[0]["status"], "healthy")
            self.assertTrue(results[0]["restarted"])
            self.assertEqual(docker.calls.count(("restart_container", container)), 1)

    def test_verify_fails_when_health_stays_bad_after_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            container = "cicd-pps7-api-api-staging"
            platform = PlatformConfig(
                state_dir=root / "state",
                network_prefix="cicd",
                image_namespace="cicd",
                curl_image="curlimages/curl",
                nginx=NginxSettings(),
                backups={},
            )
            docker = FakeDocker(existing={container}, running={container: True}, health_statuses=[500, 500])
            engine = DeploymentEngine(platform, docker)
            project = ProjectSpec(
                "pps7-api",
                [],
                [ServiceSpec("api", "node", 3000, health_check=HealthCheck(path="/health"))],
            )
            state = engine._state_document(project, resolve_environment("staging"), "cicd-pps7-api-staging")
            state["services"] = {"api": {"name": "api", "type": "node", "container": container}}
            engine.state.save(project.name, "staging", state)

            with self.assertRaisesRegex(RuntimeError, "Service verification failed"):
                engine.maintain(project, resolve_environment("staging"), operation="verify")

            self.assertEqual(docker.calls.count(("restart_container", container)), 1)


if __name__ == "__main__":
    unittest.main()
