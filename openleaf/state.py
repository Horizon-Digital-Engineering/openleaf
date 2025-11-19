"""Shared Leaf state management primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from threading import RLock
from typing import Any, Dict, List

__all__ = ["LeafState", "StateStore"]


@dataclass(slots=True)
class LeafState:
    """Represents the decoded telemetry values for a Leaf."""

    soc_true: float = 0.0
    soh: float = 0.0
    pack_voltage: float = 0.0
    pack_temp_c: float = 0.0
    cell_delta_mv: float = 0.0
    cell_voltages: List[float] = field(default_factory=list)
    dtcs: List[str] = field(default_factory=list)


class StateStore:
    """Thread-safe wrapper around :class:`LeafState`."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = LeafState()

    def update(self, **kwargs: Any) -> None:
        """Update attributes on the internal state if they exist."""

        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)

    def snapshot(self) -> Dict[str, Any]:
        """Return a copy of the current state as a dictionary."""

        with self._lock:
            return asdict(self._state)
