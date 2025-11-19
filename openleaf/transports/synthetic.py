"""Synthetic transport implementation producing fake Leaf telemetry."""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, Iterable, Iterator, List

from .base import Transport


class SyntheticTransport(Transport):
    """Deterministic-ish transport for development and testing."""

    def __init__(self, update_interval_sec: float = 0.5, cell_count: int = 96) -> None:
        self.update_interval_sec = update_interval_sec
        self._phase = 0.0
        self.cell_count = max(1, cell_count)

    def loop(self) -> Iterable[Dict[str, Any]]:
        return self._generator()

    def _generator(self) -> Iterator[Dict[str, Any]]:
        while True:
            soc = 50 + 30 * math.sin(self._phase)
            pack_voltage = 360 + (10 * math.sin(self._phase / 2))
            pack_temp = 25 + random.uniform(-2.0, 2.0)
            cell_voltages = self._generate_cell_voltages()
            cell_delta = (max(cell_voltages) - min(cell_voltages)) * 1000
            self._phase += 0.1

            dtcs = self._generate_dtcs()

            yield {
                "soc_true": round(max(0.0, min(100.0, soc)), 2),
                "soh": 72.0,
                "pack_voltage": round(pack_voltage, 2),
                "pack_temp_c": round(pack_temp, 2),
                "cell_delta_mv": round(cell_delta, 2),
                "cell_voltages": [round(value, 3) for value in cell_voltages],
                "dtcs": dtcs,
            }

            time.sleep(self.update_interval_sec)

    def _generate_cell_voltages(self) -> List[float]:
        base_voltage = 3.8 + 0.02 * math.sin(self._phase / 3)
        noise = [random.uniform(-0.015, 0.015) for _ in range(self.cell_count)]
        return [base_voltage + jitter for jitter in noise]

    def _generate_dtcs(self) -> List[str]:
        # Simple oscillating sample codes for UI visualization.
        active = math.sin(self._phase / 5) > 0.6
        if not active:
            return []
        sample_codes = ["P0A80", "C118C", "B29C1"]
        count = random.randint(1, len(sample_codes))
        return sample_codes[:count]
