from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

from .base import Provider
from ..model import ServiceSpec
from ..util import resolve_within


class NodeProvider(Provider):
    resource_type = "node"

    def _container_name(self, context: Any, spec: ServiceSpec) -> str:
        return f"{context.platform.network_prefix}-{context.project.docker_name}-{spec.docker_name}-{context.environment.docker_name}"

    def _image_tag(self, context: Any, spec: ServiceSpec) -> str:
        return (
            f"{context.platform.image_namespace}/{context.project.docker_name}-{spec.docker_name}:"
            f"{context.environment.docker_name}-{context.build_number}"
        ).lower()

    def _dependency_environment(self, context: Any, spec: ServiceSpec) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for dependency in spec.depends_on:
            resource = context.resources[dependency]
            if resource["type"] == "mongo":
                values.update({"MONGO_URI": resource["uri"], "MONGO_DB_NAME": resource["database"]})
            elif resource["type"] == "redis":
                values.update({
                    "REDIS_URL": resource["uri"],
                    "REDIS_URI": resource["uri"],  # compatibility for current applications
                })
        return values

    def _wait_for_health(self, context: Any, spec: ServiceSpec, container: str) -> None:
        health = spec.health_check
        if not health:
            return
        url = f"http://{container}:{spec.port}{health.path}"
        deadline = time.monotonic() + health.timeout
        last_status = None
        while time.monotonic() < deadline:
            last_status = context.docker.http_status(context.network, context.platform.curl_image, url)
            if last_status == health.status_code:
                return
            time.sleep(2)
        raise RuntimeError(
            f"Health check failed for {spec.name}: expected HTTP {health.status_code} at {health.path}, got {last_status}"
        )

    def deploy(self, context: Any, spec: ServiceSpec, previous: Dict[str, Any]) -> Dict[str, Any]:
        workspace = Path(context.workspace).resolve()
        dockerfile = resolve_within(workspace, spec.dockerfile)
        build_context = resolve_within(workspace, spec.build_context)
        if not dockerfile.is_file():
            raise FileNotFoundError(f"Dockerfile not found: {dockerfile}")
        image = self._image_tag(context, spec)
        container = self._container_name(context, spec)
        context.docker.build_image(image, str(dockerfile), str(build_context), spec.build_args)
        environment = dict(spec.env)
        environment.update(self._dependency_environment(context, spec))
        if spec.inject_base_path:
            environment["BASE_PATH"] = context.router.route_path(context.project.name, context.environment, spec.name)
        context.docker.run_container(
            name=container,
            image=image,
            network=context.network,
            labels=context.labels("service", spec.name),
            environment=environment,
            volumes=spec.volumes,
        )
        self._wait_for_health(context, spec, container)
        route = ""
        if spec.route_enabled:
            route = context.router.deploy(
                project=context.project.name,
                environment=context.environment,
                service=spec.name,
                container=container,
                port=spec.port,
                network=context.network,
            )
        return {"name": spec.name, "type": self.resource_type, "container": container, "image": image, "route": route}

    def destroy(self, context: Any, state: Dict[str, Any]) -> None:
        name = state.get("name")
        if name:
            context.router.remove(context.project.name, context.environment, name)
        container = state.get("container")
        if container:
            context.docker.remove_container(container)
