from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from deploylib.config import NginxSettings, PlatformConfig
from deploylib.engine import DeploymentEngine
from deploylib.environment import resolve_environment
from deploylib.model import InfrastructureSpec, ProjectSpec, ServiceSpec
from deploylib.providers.node import NodeProvider
from deploylib.providers.redis import RedisProvider


class TopologyTests(unittest.TestCase):
    def _platform(self, state_dir: Path) -> PlatformConfig:
        return PlatformConfig(
            state_dir=state_dir,
            network_prefix="cicd",
            image_namespace="cicd",
            curl_image="curlimages/curl",
            nginx=NginxSettings(),
            backups={},
        )

    def test_each_environment_uses_its_own_network(self):
        project = ProjectSpec("demo", [], [])
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = DeploymentEngine(self._platform(Path(temp_dir)), docker=SimpleNamespace())
            self.assertEqual(engine._network_name(project, resolve_environment("develop")), "cicd-demo-dev")
            self.assertRegex(engine._network_name(project, resolve_environment("feature/auth")), r"^cicd-demo-feature-auth-[0-9a-f]{6}$")

    def test_redis_is_named_per_environment(self):
        provider = RedisProvider()
        project = ProjectSpec("demo", [], [])
        spec = InfrastructureSpec("redis", "redis", "7", None)
        dev_context = SimpleNamespace(platform=SimpleNamespace(network_prefix="cicd"), project=project, environment=resolve_environment("develop"))
        feature_context = SimpleNamespace(platform=SimpleNamespace(network_prefix="cicd"), project=project, environment=resolve_environment("feature/auth"))
        self.assertNotEqual(provider._container_name(dev_context, spec), provider._container_name(feature_context, spec))
        self.assertIn("feature-auth", provider._container_name(feature_context, spec))

    def test_node_does_not_inject_redis_prefix(self):
        provider = NodeProvider()
        service = ServiceSpec("api", "node", 3000, depends_on=["redis"])
        context = SimpleNamespace(resources={"redis": {"type": "redis", "uri": "redis://redis:6379/0"}})
        values = provider._dependency_environment(context, service)
        self.assertEqual(values["REDIS_URL"], "redis://redis:6379/0")
        self.assertNotIn("REDIS_PREFIX", values)


if __name__ == "__main__":
    unittest.main()
