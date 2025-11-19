"""Base transport definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable


class Transport(ABC):
    """Generic interface for how data enters the system."""

    @abstractmethod
    def loop(self) -> Iterable[Dict[str, Any]]:
        """Blocking generator yielding decoded updates forever."""

    def send_command(self, command: str, **_: Any) -> None:
        """Optional command hook; defaults to a no-op."""

        return None
