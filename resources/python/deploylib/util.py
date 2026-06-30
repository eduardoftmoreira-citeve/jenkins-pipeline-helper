from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict


def docker_safe_name(value: str, max_length: int = 48) -> str:
    """Return a stable name safe for Docker resources, labels, and route file names."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized:
        raise ValueError("Name cannot be empty after Docker normalization")
    if len(normalized) <= max_length:
        return normalized
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{normalized[: max_length - 9].rstrip('-')}-{digest}"


def resolve_within(base: Path, candidate: str) -> Path:
    """Resolve a project-relative path and reject paths escaping the Jenkins workspace."""
    root = base.resolve()
    target = (root / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path must stay within workspace: {candidate}") from exc
    return target


def string_map(value: Any, field_name: str) -> Dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return {str(key): str(item) for key, item in value.items()}
