from __future__ import annotations

from dataclasses import dataclass
import hashlib

from .util import docker_safe_name


class UnsupportedBranch(ValueError):
    pass


@dataclass(frozen=True)
class Environment:
    branch: str
    name: str
    kind: str
    shared_mongo: bool
    ephemeral: bool

    @property
    def docker_name(self) -> str:
        return docker_safe_name(self.name)


PRODUCTION_BRANCHES = frozenset({"main", "master", "prod", "production"})
STAGING_BRANCHES = frozenset({"stage", "staging"})
DEVELOPMENT_BRANCHES = frozenset({"dev", "develop", "development"})


def normalize_branch(raw_branch: str) -> str:
    branch = (raw_branch or "").strip()
    for prefix in ("refs/heads/", "origin/"):
        if branch.startswith(prefix):
            branch = branch[len(prefix):]
    if not branch:
        raise UnsupportedBranch("Branch name is empty")
    return branch


def resolve_environment(raw_branch: str) -> Environment:
    """Map the agreed Git branch convention to an explicit deployment environment."""
    branch = normalize_branch(raw_branch)
    if branch in PRODUCTION_BRANCHES:
        return Environment(branch=branch, name="prod", kind="production", shared_mongo=False, ephemeral=False)
    if branch in DEVELOPMENT_BRANCHES:
        return Environment(branch=branch, name="dev", kind="development", shared_mongo=True, ephemeral=False)
    if branch in STAGING_BRANCHES:
        return Environment(branch=branch, name="staging", kind="staging", shared_mongo=True, ephemeral=False)
    for prefix in ("feature/", "bugfix/"):
        if branch.startswith(prefix) and len(branch) > len(prefix):
            suffix = branch[len(prefix):]
            # Git allows names that normalize to the same Docker token. Keep the raw
            # branch's identity with a deterministic short hash.
            digest = hashlib.sha1(branch.encode("utf-8")).hexdigest()[:6]
            return Environment(
                branch=branch,
                name=f"{prefix[:-1]}-{docker_safe_name(suffix, max_length=38)}-{digest}",
                kind=prefix[:-1],
                shared_mongo=True,
                ephemeral=True,
            )
    raise UnsupportedBranch(
        "Unsupported branch. Allowed: main/master/prod/production, dev/develop/development, "
        "stage/staging, feature/*, bugfix/*. "
        f"Received: {branch}"
    )
