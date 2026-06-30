from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from .environment import Environment
from .util import resolve_within


@dataclass(frozen=True)
class NginxSettings:
    enabled: bool = False
    container: str = "nginx-proxy"
    locations_dir: Optional[str] = None
    route_prefix: str = "deploy"


@dataclass(frozen=True)
class BackupPolicy:
    """Retention and verification policy shared by archive-capable providers."""

    enabled: bool = False
    daily_retention_days: int = 0
    weekly_retention_weeks: int = 0
    monthly_retention_months: int = 0
    verify_restore: bool = False


@dataclass(frozen=True)
class ProviderBackupSettings:
    """Platform-owned backup settings for one provider type."""

    root_dir: Path
    policies: Mapping[str, BackupPolicy]

    def policy_for(self, environment: Environment) -> BackupPolicy:
        return self.policies.get(environment.kind, BackupPolicy())


@dataclass(frozen=True)
class PlatformConfig:
    state_dir: Path
    network_prefix: str
    image_namespace: str
    curl_image: str
    nginx: NginxSettings
    backups: Mapping[str, ProviderBackupSettings]

    def backup_settings_for(self, provider_type: str) -> Optional[ProviderBackupSettings]:
        return self.backups.get(provider_type)


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file must contain a mapping: {path}")
    return data


def load_application_config(workspace: Path) -> Dict[str, Any]:
    """Load the one application-owned configuration file used by every branch."""
    workspace = workspace.resolve()
    return _read_yaml(resolve_within(workspace, "app-config.yaml"))


def _positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be zero or greater")
    return parsed


def _backup_policy(raw: Any, provider_type: str, name: str) -> BackupPolicy:
    if raw is None:
        return BackupPolicy()
    if not isinstance(raw, dict):
        raise ValueError(f"backups.providers.{provider_type}.policies.{name} must be a mapping")
    return BackupPolicy(
        enabled=bool(raw.get("enabled", False)),
        daily_retention_days=_positive_int(
            raw.get("daily_retention_days", 0),
            f"backups.providers.{provider_type}.policies.{name}.daily_retention_days",
        ),
        weekly_retention_weeks=_positive_int(
            raw.get("weekly_retention_weeks", 0),
            f"backups.providers.{provider_type}.policies.{name}.weekly_retention_weeks",
        ),
        monthly_retention_months=_positive_int(
            raw.get("monthly_retention_months", 0),
            f"backups.providers.{provider_type}.policies.{name}.monthly_retention_months",
        ),
        verify_restore=bool(raw.get("verify_restore", False)),
    )


def _provider_backup_settings(raw: Any, provider_type: str) -> ProviderBackupSettings:
    if not isinstance(raw, dict):
        raise ValueError(f"backups.providers.{provider_type} must be a mapping")
    root_dir = raw.get("root_dir")
    if not isinstance(root_dir, str) or not root_dir.strip():
        raise ValueError(f"backups.providers.{provider_type}.root_dir must be a non-empty path")
    policies_raw = raw.get("policies", {}) or {}
    if not isinstance(policies_raw, dict):
        raise ValueError(f"backups.providers.{provider_type}.policies must be a mapping")
    return ProviderBackupSettings(
        root_dir=Path(root_dir).expanduser(),
        policies={
            environment_kind: _backup_policy(policy, provider_type, environment_kind)
            for environment_kind, policy in policies_raw.items()
        },
    )


def load_platform_config(path: Path) -> PlatformConfig:
    raw = _read_yaml(path)
    nginx_raw = raw.get("nginx", {}) or {}
    if not isinstance(nginx_raw, dict):
        raise ValueError("platform nginx must be a mapping")
    backups_raw = raw.get("backups", {}) or {}
    if not isinstance(backups_raw, dict):
        raise ValueError("platform backups must be a mapping")
    provider_backups_raw = backups_raw.get("providers", {}) or {}
    if not isinstance(provider_backups_raw, dict):
        raise ValueError("backups.providers must be a mapping")

    state_dir = raw.get("state_dir")
    if not isinstance(state_dir, str) or not state_dir.strip():
        raise ValueError("platform state_dir is required")
    nginx_enabled = bool(nginx_raw.get("enabled", False))
    locations_dir = nginx_raw.get("locations_dir")
    if nginx_enabled and (not isinstance(locations_dir, str) or not locations_dir.strip()):
        raise ValueError("nginx.locations_dir is required when nginx.enabled is true")

    backups = {
        provider_type: _provider_backup_settings(settings, provider_type)
        for provider_type, settings in provider_backups_raw.items()
    }
    for provider_type, settings in backups.items():
        production_policy = settings.policies.get("production", BackupPolicy())
        if production_policy.enabled and production_policy.daily_retention_days == 0:
            raise ValueError(
                f"production backups for provider '{provider_type}' need daily_retention_days greater than zero"
            )

    return PlatformConfig(
        state_dir=Path(state_dir).expanduser(),
        network_prefix=str(raw.get("network_prefix", "cicd")),
        image_namespace=str(raw.get("image_namespace", "cicd")),
        curl_image=str(raw.get("curl_image", "curlimages/curl:8.10.1")),
        nginx=NginxSettings(
            enabled=nginx_enabled,
            container=str(nginx_raw.get("container", "nginx-proxy")),
            locations_dir=locations_dir,
            route_prefix=str(nginx_raw.get("route_prefix", "deploy")).strip("/"),
        ),
        backups=backups,
    )
