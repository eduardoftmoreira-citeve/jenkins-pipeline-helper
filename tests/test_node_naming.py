from __future__ import annotations

from types import SimpleNamespace
import unittest

from deploylib.environment import resolve_environment
from deploylib.model import ProjectSpec, ServiceSpec
from deploylib.providers.node import NodeProvider


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


if __name__ == "__main__":
    unittest.main()
