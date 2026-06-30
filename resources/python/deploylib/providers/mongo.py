from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Dict

from .base import Provider
from ..model import InfrastructureSpec


class MongoProvider(Provider):
    resource_type = "mongo"
    capabilities = frozenset({"deploy", "destroy", "backup", "verify_backup", "restore"})

    @staticmethod
    def _mongo_safe_identifier(value: str, max_length: int = 54) -> str:
        """Mongo-specific naming stays with this provider, not shared utilities."""
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
        if not normalized:
            raise ValueError("Mongo identifier cannot be empty")
        if len(normalized) <= max_length:
            return normalized
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
        return f"{normalized[: max_length - 9].rstrip('_')}_{digest}"

    def _image(self, spec: InfrastructureSpec) -> str:
        if spec.image:
            return spec.image
        if not spec.version:
            raise ValueError(f"Mongo infrastructure '{spec.name}' needs version or image")
        return f"mongo:{spec.version}"

    def _container_name(self, context: Any, spec: InfrastructureSpec) -> str:
        scope = "shared" if context.environment.shared_mongo else context.environment.docker_name
        return f"{context.platform.network_prefix}-{context.project.docker_name}-{spec.docker_name}-{scope}"

    @staticmethod
    def _volume_name(container: str) -> str:
        return f"{container}-data"

    def _database_name(self, context: Any, spec: InfrastructureSpec) -> str:
        return self._mongo_safe_identifier(f"{context.project.name}_{spec.name}_{context.environment.name}")

    def _wait_for_mongo(self, context: Any, container: str) -> None:
        command = ["mongosh", "--quiet", "--eval", "db.adminCommand({ping: 1})"]
        last_error = "MongoDB did not become ready"
        for _ in range(30):
            result = context.docker.exec(container, command, check=False)
            if result.returncode == 0:
                return
            last_error = result.stderr.strip() or result.stdout.strip() or last_error
            time.sleep(2)
        raise RuntimeError(f"MongoDB is not ready in {container}: {last_error}")

    def _run_admin_script(self, context: Any, container: str, script: str) -> None:
        self._wait_for_mongo(context, container)
        context.docker.exec(container, ["mongosh", "--quiet", "--eval", script])

    def deploy(self, context: Any, spec: InfrastructureSpec, previous: Dict[str, Any]) -> Dict[str, Any]:
        image = self._image(spec)
        container = self._container_name(context, spec)
        volume = self._volume_name(container) if spec.data_volume else ""
        if context.docker.container_exists(container):
            context.log(f"Mongo container {container} already exists; validating image and running state")
            existing_image = context.docker.container_image(container)
            if existing_image and existing_image != image:
                raise RuntimeError(
                    f"Mongo container {container} uses {existing_image}, but config requests {image}. "
                    "Upgrade it deliberately; this deployer will not replace persistent infrastructure automatically."
                )
            if not context.docker.running(container):
                raise RuntimeError(f"Mongo container exists but is not running: {container}")
        else:
            context.log(f"Creating Mongo container {container} from {image}")
            context.docker.run_container(
                name=container,
                image=image,
                network=context.network,
                labels=context.labels("infrastructure", spec.name),
                environment=dict(spec.env),
                volumes=[f"{volume}:/data/db"] if volume else [],
            )

        # Shared non-production Mongo joins each active environment network. Its
        # databases are isolated by name, while Redis is container-isolated.
        context.log(f"Connecting Mongo container {container} to {context.network}")
        context.docker.connect_network(context.network, container)
        context.log(f"Waiting for Mongo readiness in {container}")
        self._wait_for_mongo(context, container)
        database = self._database_name(context, spec)
        context.log(f"Mongo database selected: {database}")
        return {
            "name": spec.name,
            "type": self.resource_type,
            "container": container,
            "scope": "shared" if context.environment.shared_mongo else "dedicated",
            "database": database,
            "uri": f"mongodb://{container}:27017/{database}",
            "image": image,
            "volume": volume,
        }

    def backup(self, context: Any, spec: InfrastructureSpec, state: Dict[str, Any], destination: Path) -> None:
        container = state.get("container")
        database = state.get("database")
        if not container or not database:
            raise RuntimeError("Mongo state is incomplete; cannot create backup")
        if not context.docker.container_exists(container):
            raise RuntimeError(f"Mongo container is missing: {container}")
        self._wait_for_mongo(context, container)
        context.docker.exec_to_file(
            container,
            ["mongodump", "--quiet", "--gzip", "--archive", "--db", database],
            destination,
        )
        if not destination.exists() or destination.stat().st_size == 0:
            raise RuntimeError("Mongo backup command completed but produced an empty archive")

    def verify_backup(self, context: Any, spec: InfrastructureSpec, state: Dict[str, Any], archive: Path) -> None:
        """Restore to a disposable Mongo container before accepting a production archive."""
        source_image = state.get("image") or self._image(spec)
        verifier_name = self._mongo_safe_identifier(
            f"backup_verify_{context.project.name}_{context.environment.name}_{int(time.time())}",
            max_length=56,
        )
        database = state.get("database")
        if not database:
            raise RuntimeError("Mongo state is incomplete; cannot verify backup")
        try:
            context.docker.run_container(
                name=verifier_name,
                image=source_image,
                network=context.network,
                labels=context.labels("backup-verification", spec.name),
                environment={},
                restart_policy=None,
            )
            self._wait_for_mongo(context, verifier_name)
            archive_name = "/tmp/backup.archive.gz"
            context.docker.copy_to_container(verifier_name, archive, archive_name)
            context.docker.exec(verifier_name, ["mongorestore", "--quiet", "--gzip", f"--archive={archive_name}"])
            verification = context.docker.exec(
                verifier_name,
                [
                    "mongosh", "--quiet", "--eval",
                    f"const names=db.adminCommand({{listDatabases: 1}}).databases.map(x => x.name); if (!names.includes({json.dumps(database)})) quit(1);",
                ],
                check=False,
            )
            if verification.returncode != 0:
                raise RuntimeError(f"Backup verification did not restore database {database}")
        finally:
            context.docker.remove_container(verifier_name)

    def restore(self, context: Any, spec: InfrastructureSpec, state: Dict[str, Any], archive: Path) -> None:
        container = state.get("container")
        database = state.get("database")
        if not container or not database or not context.docker.container_exists(container):
            raise RuntimeError("Mongo restore target is missing")
        self._wait_for_mongo(context, container)
        archive_name = "/tmp/restore.archive.gz"
        context.docker.copy_to_container(container, archive, archive_name)
        try:
            context.docker.exec(
                container,
                [
                    "mongorestore", "--quiet", "--gzip", f"--archive={archive_name}",
                    "--drop", "--nsInclude", f"{database}.*",
                ],
            )
        finally:
            context.docker.exec(container, ["rm", "-f", archive_name], check=False)

    def destroy(self, context: Any, state: Dict[str, Any]) -> None:
        # Orphan cleanup removes this environment's database, never shared Mongo itself.
        container = state.get("container")
        database = state.get("database")
        if not container or not database or not context.docker.container_exists(container):
            return
        self._run_admin_script(
            context,
            container,
            f"const target=db.getSiblingDB({json.dumps(database)}); target.dropDatabase();",
        )
        if state.get("scope") == "shared":
            context.docker.disconnect_network(context.network, container)
        else:
            context.docker.remove_container(container)
            volume = state.get("volume")
            if volume:
                context.docker.remove_volume(volume)
