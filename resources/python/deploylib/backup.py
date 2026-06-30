from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Iterable, Set

from .config import BackupPolicy
from .util import docker_safe_name


class ArchiveBackupManager:
    """Provider-neutral archive storage, checksums, verification and retention."""

    def __init__(self, root_dir: Path, policy: BackupPolicy):
        self.root_dir = root_dir.expanduser()
        self.policy = policy

    def _resource_dir(self, context: Any, resource_name: str) -> Path:
        return (
            self.root_dir
            / docker_safe_name(context.project.name)
            / context.environment.docker_name
            / docker_safe_name(resource_name)
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _atomic_json(path: Path, value: Dict[str, Any]) -> None:
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def create(self, provider: Any, context: Any, spec: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        directory = self._resource_dir(context, spec.name)
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        timestamp = datetime.now(timezone.utc)
        stem = timestamp.strftime("%Y%m%dT%H%M%SZ")
        archive = directory / f"{stem}.archive.gz"
        if archive.exists():
            raise RuntimeError(f"Backup archive already exists: {archive}")
        temporary = directory / f".{stem}.archive.gz.partial"
        manifest_path = directory / f"{archive.name}.json"
        try:
            provider.backup(context, spec, state, temporary)
            os.chmod(temporary, 0o600)
            if self.policy.verify_restore:
                provider.verify_backup(context, spec, state, temporary)
            digest = self._sha256(temporary)
            os.replace(temporary, archive)
            manifest = {
                "schema_version": 2,
                "created_at": timestamp.isoformat(),
                "archive": archive.name,
                "sha256": digest,
                "project": context.project.name,
                "environment": context.environment.name,
                "branch": context.environment.branch,
                "resource": spec.name,
                "provider": provider.resource_type,
                "verified_restore": self.policy.verify_restore,
            }
            self._atomic_json(manifest_path, manifest)
        finally:
            temporary.unlink(missing_ok=True)
        self.prune(directory, now=timestamp)
        return {
            "provider": provider.resource_type,
            "resource": spec.name,
            "archive": str(archive),
            "manifest": str(manifest_path),
            "sha256": digest,
            "verified_restore": self.policy.verify_restore,
        }

    @staticmethod
    def _records(directory: Path) -> Iterable[Dict[str, Any]]:
        for manifest_path in sorted(directory.glob("*.archive.gz.json"), reverse=True):
            try:
                with manifest_path.open("r", encoding="utf-8") as handle:
                    record = json.load(handle)
                timestamp = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
                archive = directory / record["archive"]
                if archive.exists():
                    yield {"manifest_path": manifest_path, "archive_path": archive, "timestamp": timestamp, "record": record}
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                # Retention never deletes a file it cannot confidently classify.
                continue

    def _retained_paths(self, directory: Path, now: datetime) -> Set[Path]:
        keep: Set[Path] = set()
        weekly: Set[str] = set()
        monthly: Set[str] = set()
        daily_floor = now - timedelta(days=self.policy.daily_retention_days)
        weekly_floor = now - timedelta(weeks=self.policy.weekly_retention_weeks)
        monthly_floor = now - timedelta(days=31 * self.policy.monthly_retention_months)
        for item in sorted(self._records(directory), key=lambda entry: entry["timestamp"], reverse=True):
            timestamp: datetime = item["timestamp"]
            archive: Path = item["archive_path"]
            if self.policy.daily_retention_days and timestamp > daily_floor:
                keep.add(archive)
                continue
            iso_year, iso_week, _ = timestamp.isocalendar()
            week_key = f"{iso_year:04d}-{iso_week:02d}"
            if self.policy.weekly_retention_weeks and timestamp > weekly_floor and week_key not in weekly:
                weekly.add(week_key)
                keep.add(archive)
                continue
            month_key = timestamp.strftime("%Y-%m")
            if self.policy.monthly_retention_months and timestamp > monthly_floor and month_key not in monthly:
                monthly.add(month_key)
                keep.add(archive)
        return keep

    def prune(self, directory: Path, now: datetime) -> int:
        keep = self._retained_paths(directory, now)
        removed = 0
        for item in list(self._records(directory)):
            archive: Path = item["archive_path"]
            if archive in keep:
                continue
            archive.unlink(missing_ok=True)
            item["manifest_path"].unlink(missing_ok=True)
            removed += 1
        return removed

    @staticmethod
    def read_manifest(archive: Path) -> Dict[str, Any]:
        archive = archive.resolve()
        manifest_path = archive.with_name(f"{archive.name}.json")
        if not archive.exists() or not manifest_path.exists():
            raise FileNotFoundError("Backup archive or manifest is missing")
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        expected = manifest.get("sha256")
        if not expected or ArchiveBackupManager._sha256(archive) != expected:
            raise RuntimeError("Backup archive checksum does not match its manifest")
        provider = manifest.get("provider")
        if not isinstance(provider, str) or not provider:
            raise RuntimeError("Backup manifest is missing its provider type; create a new backup before using generic restore")
        return manifest

    def validate_archive(self, archive: Path) -> Dict[str, Any]:
        archive = archive.resolve()
        root = self.root_dir.resolve()
        try:
            archive.relative_to(root)
        except ValueError as exc:
            raise ValueError("Restore archive must live under the configured backup root for its provider") from exc
        return self.read_manifest(archive)
