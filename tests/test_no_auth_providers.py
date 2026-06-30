from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from deploylib.model import InfrastructureSpec, ProjectSpec
from deploylib.providers.mongo import MongoProvider
from deploylib.providers.redis import RedisProvider


class _Result:
    returncode = 0
    stdout = "PONG\n"
    stderr = ""


class _Docker:
    def __init__(self) -> None:
        self.runs = []
        self.executions = []

    def container_exists(self, _name):
        return False

    def run_container(self, **kwargs):
        self.runs.append(kwargs)

    def connect_network(self, _network, _container):
        return None

    def exec(self, _container, command, check=True):
        self.executions.append(command)
        if command[:2] == ["redis-cli", "--raw"]:
            return _Result()
        result = _Result()
        result.stdout = ""
        return result


class UnauthenticatedProviderTests(unittest.TestCase):
    def _context(self):
        project = ProjectSpec("demo", [], [])
        environment = SimpleNamespace(
            shared_mongo=False,
            docker_name="prod",
            name="prod",
        )
        return SimpleNamespace(
            platform=SimpleNamespace(network_prefix="cicd"),
            project=project,
            environment=environment,
            network="cicd-demo-prod",
            labels=lambda category, name: {"category": category, "name": name},
            docker=_Docker(),
        )

    def test_mongo_uses_no_credentials_or_root_init_variables(self):
        context = self._context()
        state = MongoProvider().deploy(context, InfrastructureSpec("mongo", "mongo", "8", None), {})
        self.assertEqual(context.docker.runs[0]["environment"], {})
        self.assertNotIn("@", state["uri"])
        self.assertNotIn("username", state)
        self.assertNotIn("password", state)

    def test_redis_uses_no_requirepass_or_password_uri(self):
        context = self._context()
        state = RedisProvider().deploy(context, InfrastructureSpec("redis", "redis", "7", None), {})
        self.assertEqual(context.docker.runs[0]["command"], ["redis-server", "--appendonly", "yes"])
        self.assertEqual(state["uri"], "redis://cicd-demo-redis-prod:6379/0")
        self.assertNotIn("password", state)


if __name__ == "__main__":
    unittest.main()
