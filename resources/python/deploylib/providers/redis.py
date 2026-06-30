from __future__ import annotations

import time
from typing import Any, Dict

from .base import Provider
from ..model import InfrastructureSpec


class RedisProvider(Provider):
    resource_type = "redis"

    def _image(self, spec: InfrastructureSpec) -> str:
        if spec.image:
            return spec.image
        if not spec.version:
            raise ValueError(f"Redis infrastructure '{spec.name}' needs version or image")
        return f"redis:{spec.version}"

    def _container_name(self, context: Any, spec: InfrastructureSpec) -> str:
        # Redis is intentionally one container per environment, never prefix-shared.
        return f"{context.platform.network_prefix}-{context.project.docker_name}-{spec.docker_name}-{context.environment.docker_name}"

    @staticmethod
    def _volume_name(container: str) -> str:
        return f"{container}-data"

    def deploy(self, context: Any, spec: InfrastructureSpec, previous: Dict[str, Any]) -> Dict[str, Any]:
        image = self._image(spec)
        container = self._container_name(context, spec)
        volume = self._volume_name(container) if spec.data_volume else ""
        if context.docker.container_exists(container):
            existing_image = context.docker.container_image(container)
            if existing_image and existing_image != image:
                raise RuntimeError(
                    f"Redis container {container} uses {existing_image}, but config requests {image}. "
                    "Upgrade it deliberately; this deployer will not replace persistent infrastructure automatically."
                )
            if not context.docker.running(container):
                raise RuntimeError(f"Redis container exists but is not running: {container}")
        else:
            context.docker.run_container(
                name=container,
                image=image,
                network=context.network,
                labels=context.labels("infrastructure", spec.name),
                environment=dict(spec.env),
                volumes=[f"{volume}:/data"] if volume else [],
                command=["redis-server", "--appendonly", "yes"],
            )
        last_error = "Redis did not become ready"
        for _ in range(30):
            result = context.docker.exec(container, ["redis-cli", "--raw", "PING"], check=False)
            if result.returncode == 0 and result.stdout.strip() == "PONG":
                break
            last_error = result.stderr.strip() or result.stdout.strip() or last_error
            time.sleep(2)
        else:
            raise RuntimeError(f"Redis is not ready in {container}: {last_error}")
        return {
            "name": spec.name,
            "type": self.resource_type,
            "container": container,
            "scope": "environment",
            "uri": f"redis://{container}:6379/0",
            "image": image,
            "volume": volume,
        }

    def destroy(self, context: Any, state: Dict[str, Any]) -> None:
        container = state.get("container")
        if container:
            context.docker.remove_container(container)
        volume = state.get("volume")
        if volume:
            context.docker.remove_volume(volume)
