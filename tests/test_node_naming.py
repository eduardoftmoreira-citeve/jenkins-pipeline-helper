from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from deploylib.environment import resolve_environment
from deploylib.model import HealthCheck, ProjectSpec, ServiceSpec
from deploylib.providers.node import NodeProvider


class _Docker:
    def __init__(self) -> None:
        self.builds = []
        self.runs = []

    def build_image(self, image, dockerfile, build_context, build_args):
        self.builds.append((image, dockerfile, build_context, build_args))

    def run_container(self, **kwargs):
        self.runs.append(kwargs)

    def http_status(self, _network, _image, _url):
        return 200


class _Router:
    def __init__(self) -> None:
        self.deploys = []

    def route_path(self, project, environment, service):
        return f"/piloto-cicd/{project}/{environment.docker_name}/{service}/"

    def deploy(self, **kwargs):
        self.deploys.append(kwargs)
        return self.route_path(kwargs["project"], kwargs["environment"], kwargs["service"])


class NodeNamingTests(unittest.TestCase):
    def _context(self, project_name: str):
        return SimpleNamespace(
            platform=SimpleNamespace(network_prefix="cicd", image_namespace="cicd"),
            project=ProjectSpec(project_name, [], []),
            environment=resolve_environment("staging"),
            build_number="43",
        )

    def test_includes_api_service_suffix_from_container_and_image(self):
        provider = NodeProvider()
        spec = ServiceSpec("api", "node", 3000)
        context = self._context("pps7-api")
        self.assertEqual(provider._container_name(context, spec), "cicd-pps7-api-api-staging")
        self.assertEqual(provider._image_tag(context, spec), "cicd/pps7-api-api:staging-43")

    def test_keeps_service_segment_when_a_project_has_multiple_distinct_services(self):
        provider = NodeProvider()
        spec = ServiceSpec("worker", "node", 3000)
        context = self._context("pps7-api")
        self.assertEqual(provider._container_name(context, spec), "cicd-pps7-api-worker-staging")
        self.assertEqual(provider._image_tag(context, spec), "cicd/pps7-api-worker:staging-43")

    def test_project_without_service_suffix_remains_unambiguous(self):
        provider = NodeProvider()
        spec = ServiceSpec("api", "node", 3000)
        context = self._context("pps7")
        self.assertEqual(provider._container_name(context, spec), "cicd-pps7-api-staging")

    def test_deploy_builds_runs_injects_dependencies_and_routes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            dockerfile = workspace / "Dockerfile"
            dockerfile.write_text("FROM node:22-alpine\n", encoding="utf-8")
            docker = _Docker()
            router = _Router()
            context = SimpleNamespace(
                platform=SimpleNamespace(
                    network_prefix="cicd",
                    image_namespace="cicd",
                    curl_image="curlimages/curl",
                ),
                project=ProjectSpec("pps7-api", [], []),
                environment=resolve_environment("staging"),
                build_number="43",
                workspace=workspace,
                network="cicd-pps7-api-staging",
                resources={
                    "mongo": {
                        "type": "mongo",
                        "uri": "mongodb://mongo:27017/db",
                        "database": "db",
                    },
                    "redis": {
                        "type": "redis",
                        "uri": "redis://redis:6379/0",
                    },
                },
                docker=docker,
                router=router,
                labels=lambda category, component: {"category": category, "component": component},
                log=lambda message: None,
            )
            spec = ServiceSpec(
                "api",
                "node",
                3000,
                depends_on=["mongo", "redis"],
                health_check=HealthCheck(path="/health"),
                route_enabled=True,
                inject_base_path=True,
            )

            state = NodeProvider().deploy(context, spec, {})

            self.assertEqual(state["container"], "cicd-pps7-api-api-staging")
            self.assertEqual(docker.builds[0][0], "cicd/pps7-api-api:staging-43")
            run = docker.runs[0]
            self.assertEqual(run["name"], "cicd-pps7-api-api-staging")
            self.assertEqual(run["environment"]["MONGO_URI"], "mongodb://mongo:27017/db")
            self.assertEqual(run["environment"]["MONGO_DB_NAME"], "db")
            self.assertEqual(run["environment"]["REDIS_URL"], "redis://redis:6379/0")
            self.assertEqual(run["environment"]["BASE_PATH"], "/piloto-cicd/pps7-api/staging/api/")
            self.assertEqual(router.deploys[0]["container"], "cicd-pps7-api-api-staging")
            self.assertEqual(router.deploys[0]["port"], 3000)


if __name__ == "__main__":
    unittest.main()
