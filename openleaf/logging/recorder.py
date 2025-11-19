"""Placeholder recorder implementation for future logging support."""

from __future__ import annotations

from typing import Any, Dict


class Recorder:
    """Recorder placeholder for future raw/decoded logging functionality."""

    def record(self, data: Dict[str, Any]) -> None:  # pragma: no cover - placeholder
        raise NotImplementedError("Recorder functionality not implemented yet")
