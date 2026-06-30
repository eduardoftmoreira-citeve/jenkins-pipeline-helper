from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .util import docker_safe_name, string_map


@dataclass(frozen=True)
class HealthCheck:
    path: str = "/health"
    status_code: int = 200
    timeout: int = 60


@dataclass(frozen=True)
class InfrastructureSpec:
    name: str
    type: str
    version: Optional[str]
    image: Optional[str]
    data_volume: bool = True
    env: Dict[str, str] = field(default_factory=dict)

    @property
    def docker_name(self) -> str:
        return docker_safe_name(self.name)


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    type: str
    port: int
    dockerfile: str = "Dockerfile"
    build_context: str = "."
    build_args: Dict[str, str] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    health_check: Optional[HealthCheck] = None
    route_enabled: bool = False
    inject_base_path: bool = False
    volumes: List[str] = field(default_factory=list)

    @property
    def docker_name(self) -> str:
        return docker_safe_name(self.name)


@dataclass(frozen=True)
class ProjectSpec:
    name: str
    infrastructure: List[InfrastructureSpec]
    services: List[ServiceSpec]

    @property
    def docker_name(self) -> str:
        return docker_safe_name(self.name)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ProjectSpec":
        if not isinstance(raw, dict):
            raise ValueError("Application configuration must be a YAML mapping")
        name = raw.get("project_name") or raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("project_name is required")

        infrastructure_raw = raw.get("infrastructure", {})
        services_raw = raw.get("services", {})
        if not isinstance(infrastructure_raw, dict):
            raise ValueError("infrastructure must be a mapping")
        if not isinstance(services_raw, dict) or not services_raw:
            raise ValueError("services must be a non-empty mapping")

        infrastructure: List[InfrastructureSpec] = []
        for resource_name, value in infrastructure_raw.items():
            if not isinstance(value, dict):
                raise ValueError(f"infrastructure.{resource_name} must be a mapping")
            resource_type = str(value.get("type", "")).strip().lower()
            if not resource_type:
                raise ValueError(f"infrastructure.{resource_name}.type is required")
            if resource_type in {"mongo", "redis"} and "auth" in value:
                raise ValueError(
                    f"infrastructure.{resource_name}.auth is not supported: MongoDB and Redis run without authentication"
                )
            infrastructure.append(
                InfrastructureSpec(
                    name=str(resource_name),
                    type=resource_type,
                    version=str(value["version"]) if value.get("version") is not None else None,
                    image=str(value["image"]) if value.get("image") else None,
                    data_volume=bool(value.get("data_volume", True)),
                    env=string_map(value.get("env"), f"infrastructure.{resource_name}.env"),
                )
            )

        services: List[ServiceSpec] = []
        for service_name, value in services_raw.items():
            if not isinstance(value, dict):
                raise ValueError(f"services.{service_name} must be a mapping")
            service_type = str(value.get("type", "")).strip().lower()
            if not service_type:
                raise ValueError(f"services.{service_name}.type is required")
            try:
                port = int(value.get("port"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"services.{service_name}.port must be an integer") from exc
            if not 1 <= port <= 65535:
                raise ValueError(f"services.{service_name}.port must be between 1 and 65535")
            dependencies = value.get("depends_on", [])
            if not isinstance(dependencies, list) or not all(isinstance(item, str) and item.strip() for item in dependencies):
                raise ValueError(f"services.{service_name}.depends_on must be a list of resource names")
            health_raw = value.get("health_check")
            health = None
            if health_raw is not None:
                if not isinstance(health_raw, dict):
                    raise ValueError(f"services.{service_name}.health_check must be a mapping")
                health = HealthCheck(
                    path=str(health_raw.get("path", "/health")),
                    status_code=int(health_raw.get("status_code", 200)),
                    timeout=int(health_raw.get("timeout", 60)),
                )
                if health.timeout <= 0:
                    raise ValueError(f"services.{service_name}.health_check.timeout must be positive")
            route_raw = value.get("route", False)
            if isinstance(route_raw, dict):
                route_enabled = bool(route_raw.get("enabled", True))
                inject_base_path = bool(route_raw.get("inject_base_path", False))
            elif isinstance(route_raw, bool):
                route_enabled = route_raw
                inject_base_path = False
            else:
                raise ValueError(f"services.{service_name}.route must be a boolean or mapping")
            if inject_base_path and not route_enabled:
                raise ValueError(f"services.{service_name}.route.inject_base_path requires routing to be enabled")
            volumes = value.get("volumes", [])
            if not isinstance(volumes, list) or not all(isinstance(item, str) for item in volumes):
                raise ValueError(f"services.{service_name}.volumes must be a list of Docker volume strings")
            services.append(
                ServiceSpec(
                    name=str(service_name),
                    type=service_type,
                    port=port,
                    dockerfile=str(value.get("dockerfile", "Dockerfile")),
                    build_context=str(value.get("build_context", ".")),
                    build_args=string_map(value.get("build_args"), f"services.{service_name}.build_args"),
                    env=string_map(value.get("env"), f"services.{service_name}.env"),
                    depends_on=list(dependencies),
                    health_check=health,
                    route_enabled=route_enabled,
                    inject_base_path=inject_base_path,
                    volumes=list(volumes),
                )
            )

        known_resources = {item.name for item in infrastructure}
        for service in services:
            missing = sorted(set(service.depends_on) - known_resources)
            if missing:
                raise ValueError(f"services.{service.name} references unknown infrastructure: {', '.join(missing)}")
        return cls(name=name.strip(), infrastructure=infrastructure, services=services)
