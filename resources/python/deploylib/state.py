from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

from .util import docker_safe_name


class StateStore:
    """Atomic local deployment state. Files are 0600 because they contain app credentials."""

    def __init__(self, root: Path):
        self.root = root.expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)

    def _project_dir(self, project_name: str) -> Path:
        directory = self.root / docker_safe_name(project_name)
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        return directory

    def _path(self, project_name: str, environment_name: str) -> Path:
        return self._project_dir(project_name) / f"{docker_safe_name(environment_name)}.json"

    @contextmanager
    def project_lock(self, project_name: str) -> Iterator[None]:
        lock_path = self._project_dir(project_name) / ".deploy.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def load(self, project_name: str, environment_name: str) -> Optional[Dict[str, Any]]:
        path = self._path(project_name, environment_name)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, project_name: str, environment_name: str, value: Dict[str, Any]) -> None:
        path = self._path(project_name, environment_name)
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

    def delete(self, project_name: str, environment_name: str) -> None:
        self._path(project_name, environment_name).unlink(missing_ok=True)

    def list(self, project_name: str) -> Iterable[Dict[str, Any]]:
        directory = self._project_dir(project_name)
        for path in sorted(directory.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    yield json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Unreadable deployment state file: {path}") from exc
