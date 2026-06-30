from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from .backup import ArchiveBackupManager
from .config import PlatformConfig
from .docker import DockerClient
from .environment import Environment
from .model import ProjectSpec
from .router import NginxRouter
from .state import StateStore
from .util import docker_safe_name
from .providers.mongo import MongoProvider
from .providers.node import NodeProvider
from .providers.redis import RedisProvider


@dataclass
class DeploymentContext:
    project: ProjectSpec
    environment: Environment
    platform: PlatformConfig
    docker: DockerClient
    router: NginxRouter
    workspace: Path
    build_number: str
    network: str
    resources: Dict[str, Dict[str, Any]]
    reporter: Callable[[str], None]

    def labels(self, category: str, component: str) -> Dict[str, str]:
        return {
            "io.cicd.managed": "true",
            "io.cicd.project": self.project.docker_name,
            "io.cicd.environment": self.environment.docker_name,
            "io.cicd.category": category,
            "io.cicd.component": docker_safe_name(component),
        }

    def log(self, message: str) -> None:
        self.reporter(message)

    def public_route_url(self, route: str) -> str:
        return self.router.public_url(route)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers = {"mongo": MongoProvider(), "redis": RedisProvider(), "node": NodeProvider()}

    def get(self, provider_type: str):
        try:
            return self._providers[provider_type]
        except KeyError as exc:
            supported = ", ".join(sorted(self._providers))
            raise ValueError(f"No provider registered for '{provider_type}'. Supported now: {supported}") from exc


class DeploymentEngine:
    def __init__(self, platform: PlatformConfig, docker: DockerClient, reporter: Optional[Callable[[str], None]] = None):
        self.platform = platform
        self.docker = docker
        self.registry = ProviderRegistry()
        self.state = StateStore(platform.state_dir)
        self.router = NginxRouter(docker, platform.nginx)
        self.reporter = reporter or (lambda message: None)

    def _network_name(self, project: ProjectSpec, environment: Environment) -> str:
        return f"{docker_safe_name(self.platform.network_prefix)}-{project.docker_name}-{environment.docker_name}"

    def _context(
        self,
        project: ProjectSpec,
        environment: Environment,
        workspace: Path,
        build_number: str,
        resources: Dict[str, Dict[str, Any]],
    ) -> DeploymentContext:
        return DeploymentContext(
            project=project,
            environment=environment,
            platform=self.platform,
            docker=self.docker,
            router=self.router,
            workspace=workspace,
            build_number=str(build_number),
            network=self._network_name(project, environment),
            resources=resources,
            reporter=self.reporter,
        )

    @staticmethod
    def _state_document(project: ProjectSpec, environment: Environment, network: str) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "project": project.name,
            "environment": {
                "branch": environment.branch,
                "name": environment.name,
                "kind": environment.kind,
                "ephemeral": environment.ephemeral,
                "shared_mongo": environment.shared_mongo,
            },
            "network": network,
            "resources": {},
            "services": {},
        }

    def deploy(self, project: ProjectSpec, environment: Environment, workspace: Path, build_number: str) -> Dict[str, Any]:
        with self.state.project_lock(project.name):
            return self._deploy_locked(project, environment, workspace, build_number)

    def _deploy_locked(self, project: ProjectSpec, environment: Environment, workspace: Path, build_number: str) -> Dict[str, Any]:
        previous = self.state.load(project.name, environment.name) or self._state_document(
            project, environment, self._network_name(project, environment)
        )
        resources = dict(previous.get("resources", {}))
        context = self._context(project, environment, workspace, build_number, resources)
        context.log(f"Preparing deployment for {project.name} on branch {environment.branch} -> environment {environment.name}")
        context.log(f"Ensuring Docker network {context.network}")
        self.docker.ensure_network(context.network)
        if self.platform.nginx.enabled:
            context.log(f"Connecting Nginx container {self.platform.nginx.container} to {context.network}")
            self.docker.connect_network(context.network, self.platform.nginx.container)

        state = previous
        state["network"] = context.network
        state["environment"] = {
            "branch": environment.branch,
            "name": environment.name,
            "kind": environment.kind,
            "ephemeral": environment.ephemeral,
            "shared_mongo": environment.shared_mongo,
        }
        for spec in project.infrastructure:
            context.log(f"Deploying infrastructure {spec.name} ({spec.type})")
            provider = self.registry.get(spec.type)
            resource = provider.deploy(context, spec, resources.get(spec.name, {}))
            resources[spec.name] = resource
            state["resources"] = resources
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.state.save(project.name, environment.name, state)
            context.log(f"Infrastructure {spec.name} ready: {resource.get('container', 'state saved')}")

        services = dict(previous.get("services", {}))
        for spec in project.services:
            context.log(f"Deploying service {spec.name} ({spec.type})")
            provider = self.registry.get(spec.type)
            service = provider.deploy(context, spec, services.get(spec.name, {}))
            services[spec.name] = service
            state["services"] = services
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.state.save(project.name, environment.name, state)
            context.log(f"Service {spec.name} ready: {service.get('container', 'state saved')}")
            if service.get("route"):
                context.log(f"App is live at: {context.public_route_url(service['route'])}")

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.state.save(project.name, environment.name, state)
        context.log("Pruning dangling Docker images")
        self.docker.prune_dangling_images()
        context.log(f"Deployment state saved for {project.name}/{environment.name}")
        return state

    @staticmethod
    def _environment_from_state(state: Dict[str, Any]) -> Environment:
        raw = state.get("environment", {})
        return Environment(
            branch=raw["branch"],
            name=raw["name"],
            kind=raw["kind"],
            shared_mongo=bool(raw["shared_mongo"]),
            ephemeral=bool(raw.get("ephemeral", False)),
        )

    def destroy_state(self, project: ProjectSpec, state: Dict[str, Any]) -> None:
        environment = self._environment_from_state(state)
        context = self._context(project, environment, Path.cwd(), "cleanup", dict(state.get("resources", {})))
        for service in state.get("services", {}).values():
            self.registry.get(service["type"]).destroy(context, service)
        for resource in reversed(list(state.get("resources", {}).values())):
            self.registry.get(resource["type"]).destroy(context, resource)
        if self.platform.nginx.enabled:
            self.docker.disconnect_network(context.network, self.platform.nginx.container)
        self.docker.remove_network(context.network)
        self.state.delete(project.name, environment.name)

    def cleanup_orphans(self, project: ProjectSpec, active_branches: Iterable[str]) -> int:
        with self.state.project_lock(project.name):
            active: Set[str] = set(active_branches)
            removed = 0
            for state in list(self.state.list(project.name)):
                environment = state.get("environment", {})
                if not environment.get("ephemeral"):
                    continue
                if environment.get("branch") not in active:
                    self.destroy_state(project, state)
                    removed += 1
            self.docker.prune_dangling_images()
            return removed

    def maintain(
        self,
        project: ProjectSpec,
        environment: Environment,
        *,
        operation: str,
        archive: Optional[Path] = None,
        confirmation: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Dispatch a provider-neutral maintenance operation for one environment."""
        if operation == "verify":
            return self._verify_services(project, environment)
        if operation == "backup":
            return self._backup_resources(project, environment)
        if operation == "restore":
            if archive is None:
                raise ValueError("Restore requires an archive path")
            if confirmation != environment.name:
                raise RuntimeError(f"Restore confirmation must exactly equal '{environment.name}'")
            return [self._restore_resource(project, environment, archive)]
        raise ValueError(f"Unsupported maintenance operation: {operation}")

    def _verify_services(self, project: ProjectSpec, environment: Environment) -> List[Dict[str, Any]]:
        with self.state.project_lock(project.name):
            state = self.state.load(project.name, environment.name)
            if not state:
                raise RuntimeError(f"No deployment state exists for {project.name}/{environment.name}")
            services = dict(state.get("services", {}))
            if not services:
                raise RuntimeError(f"No deployed services exist for {project.name}/{environment.name}")

            spec_by_name = {spec.name: spec for spec in project.services}
            network = state.get("network") or self._network_name(project, environment)
            results: List[Dict[str, Any]] = []
            failures: List[str] = []

            for name, service_state in services.items():
                container = service_state.get("container")
                spec = spec_by_name.get(name)
                if not container:
                    failures.append(f"{name}: state has no container name")
                    continue
                if not spec:
                    failures.append(f"{name}: service is absent from current application config")
                    continue

                self.reporter(f"Verifying service {name}: {container}")
                if not self.docker.container_exists(container):
                    failures.append(f"{name}: container is missing ({container})")
                    continue

                restarted = False
                if not self.docker.running(container):
                    self.reporter(f"Service {name} is stopped; restarting {container}")
                    self.docker.restart_container(container)
                    restarted = True
                    if not self.docker.running(container):
                        failures.append(f"{name}: container is still stopped after restart ({container})")
                        results.append(
                            {
                                "service": name,
                                "container": container,
                                "status": "stopped",
                                "restarted": restarted,
                                "health_status": None,
                                "expected_status": None,
                                "route": service_state.get("route", ""),
                            }
                        )
                        continue

                health_status = None
                expected_status = None
                if spec.health_check:
                    expected_status = spec.health_check.status_code
                    url = f"http://{container}:{spec.port}{spec.health_check.path}"
                    health_status = self.docker.http_status(network, self.platform.curl_image, url)
                    if health_status != expected_status and not restarted:
                        self.reporter(
                            f"Service {name} health returned {health_status}; restarting {container} once"
                        )
                        self.docker.restart_container(container)
                        restarted = True
                        health_status = self.docker.http_status(network, self.platform.curl_image, url)
                    if health_status != expected_status:
                        failures.append(
                            f"{name}: expected HTTP {expected_status}, got {health_status} after restart"
                        )
                        results.append(
                            {
                                "service": name,
                                "container": container,
                                "status": "unhealthy",
                                "restarted": restarted,
                                "health_status": health_status,
                                "expected_status": expected_status,
                                "route": service_state.get("route", ""),
                            }
                        )
                        continue

                results.append(
                    {
                        "service": name,
                        "container": container,
                        "status": "healthy" if spec.health_check else "running",
                        "restarted": restarted,
                        "health_status": health_status,
                        "expected_status": expected_status,
                        "route": service_state.get("route", ""),
                    }
                )

            if failures:
                details = "; ".join(failures)
                raise RuntimeError(f"Service verification failed for {project.name}/{environment.name}: {details}")
            return results

    def _backup_resources(self, project: ProjectSpec, environment: Environment) -> List[Dict[str, Any]]:
        with self.state.project_lock(project.name):
            state = self.state.load(project.name, environment.name)
            if not state:
                raise RuntimeError(f"No deployment state exists for {project.name}/{environment.name}")
            resources = dict(state.get("resources", {}))
            context = self._context(project, environment, Path.cwd(), "maintenance-backup", resources)
            spec_by_name = {spec.name: spec for spec in project.infrastructure}
            results: List[Dict[str, Any]] = []
            for name, resource_state in resources.items():
                provider_type = resource_state.get("type")
                if not isinstance(provider_type, str):
                    raise RuntimeError(f"Resource state is missing a provider type: {name}")
                settings = self.platform.backup_settings_for(provider_type)
                if settings is None:
                    continue
                policy = settings.policy_for(environment)
                if not policy.enabled:
                    continue
                provider = self.registry.get(provider_type)
                if not provider.supports("backup"):
                    raise RuntimeError(
                        f"Backup policy is enabled for provider '{provider_type}', but that provider does not support backups"
                    )
                spec = spec_by_name.get(name)
                if not spec:
                    raise RuntimeError(f"Resource state refers to unknown config resource: {name}")
                manager = ArchiveBackupManager(settings.root_dir, policy)
                results.append(manager.create(provider, context, spec, resource_state))
            if not results:
                raise RuntimeError(
                    f"No deployed resources with an enabled, supported backup policy exist for {project.name}/{environment.name}"
                )
            return results

    def _restore_resource(self, project: ProjectSpec, environment: Environment, archive: Path) -> Dict[str, Any]:
        with self.state.project_lock(project.name):
            state = self.state.load(project.name, environment.name)
            if not state:
                raise RuntimeError(f"No deployment state exists for {project.name}/{environment.name}")
            resources = dict(state.get("resources", {}))
            manifest = ArchiveBackupManager.read_manifest(archive)
            provider_type = manifest["provider"]
            settings = self.platform.backup_settings_for(provider_type)
            if settings is None:
                raise RuntimeError(f"No backup storage is configured for provider '{provider_type}'")
            manager = ArchiveBackupManager(settings.root_dir, settings.policy_for(environment))
            manifest = manager.validate_archive(archive)
            if manifest.get("project") != project.name or manifest.get("environment") != environment.name:
                raise RuntimeError("Backup manifest does not belong to the requested project/environment")
            resource_name = manifest.get("resource")
            resource_state = resources.get(resource_name)
            if not resource_state or resource_state.get("type") != provider_type:
                raise RuntimeError("Backup manifest references a resource that is not currently deployed by its recorded provider")
            spec = next((item for item in project.infrastructure if item.name == resource_name), None)
            if not spec:
                raise RuntimeError("Backup resource is absent from current application config")
            provider = self.registry.get(provider_type)
            if not provider.supports("restore"):
                raise RuntimeError(f"Provider '{provider_type}' does not support restore")
            context = self._context(project, environment, Path.cwd(), "maintenance-restore", resources)
            provider.restore(context, spec, resource_state, archive.resolve())
            return {
                "provider": provider_type,
                "resource": resource_name,
                "archive": str(archive.resolve()),
                "restored": True,
            }
