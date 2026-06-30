from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import NginxSettings
from .docker import DockerClient
from .environment import Environment
from .util import docker_safe_name


class NginxRouter:
    def __init__(self, docker: DockerClient, settings: NginxSettings):
        self.docker = docker
        self.settings = settings

    def route_path(self, project: str, environment: Environment, service: str) -> str:
        return f"/{self.settings.route_prefix}/{docker_safe_name(project)}/{environment.docker_name}/{docker_safe_name(service)}/"

    def _config_path(self, project: str, environment: Environment, service: str) -> Path:
        if not self.settings.locations_dir:
            raise RuntimeError("Nginx locations directory is not configured")
        filename = (
            f"{self.settings.route_prefix}-{docker_safe_name(project)}-"
            f"{environment.docker_name}-{docker_safe_name(service)}.conf"
        )
        return Path(self.settings.locations_dir) / filename

    def deploy(
        self,
        *,
        project: str,
        environment: Environment,
        service: str,
        container: str,
        port: int,
        network: str,
    ) -> str:
        if not self.settings.enabled:
            return ""
        self.docker.connect_network(network, self.settings.container)
        target_path = self._config_path(project, environment, service)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        base_path = self.route_path(project, environment, service)
        contents = f"""location ^~ {base_path} {{
    proxy_pass http://{container}:{port}/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix {base_path.rstrip('/')};
}}
"""
        previous: Optional[str] = target_path.read_text(encoding="utf-8") if target_path.exists() else None
        target_path.write_text(contents, encoding="utf-8")
        test = self.docker.exec(self.settings.container, ["nginx", "-t"], check=False)
        if test.returncode != 0:
            if previous is None:
                target_path.unlink(missing_ok=True)
            else:
                target_path.write_text(previous, encoding="utf-8")
            raise RuntimeError(f"Nginx rejected route configuration: {test.stderr.strip() or test.stdout.strip()}")
        self.docker.exec(self.settings.container, ["nginx", "-s", "reload"])
        return base_path

    def remove(self, project: str, environment: Environment, service: str) -> None:
        if not self.settings.enabled:
            return
        self._config_path(project, environment, service).unlink(missing_ok=True)
        self.docker.exec(self.settings.container, ["nginx", "-s", "reload"], check=False)
