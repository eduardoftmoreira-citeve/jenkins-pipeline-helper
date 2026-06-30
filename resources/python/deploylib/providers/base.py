from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, FrozenSet


class Provider(ABC):
    """Base contract for deployable resources and optional maintenance operations."""

    resource_type: str
    capabilities: FrozenSet[str] = frozenset({"deploy", "destroy"})

    def supports(self, operation: str) -> bool:
        return operation in self.capabilities

    @abstractmethod
    def deploy(self, context: Any, spec: Any, previous: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def destroy(self, context: Any, state: Dict[str, Any]) -> None:
        raise NotImplementedError

    def backup(self, context: Any, spec: Any, state: Dict[str, Any], destination: Path) -> None:
        raise NotImplementedError(f"Provider '{self.resource_type}' does not support backups")

    def verify_backup(self, context: Any, spec: Any, state: Dict[str, Any], archive: Path) -> None:
        raise NotImplementedError(f"Provider '{self.resource_type}' does not support backup verification")

    def restore(self, context: Any, spec: Any, state: Dict[str, Any], archive: Path) -> None:
        raise NotImplementedError(f"Provider '{self.resource_type}' does not support restore")
