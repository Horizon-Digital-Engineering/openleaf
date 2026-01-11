"""Shared Leaf state management primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from threading import RLock
from typing import Any, Dict, List

__all__ = ["LeafState", "StateStore"]


@dataclass(slots=True)
class LeafState:
    """Represents the decoded telemetry values for a Leaf."""

    # State of Charge (SOC) - Multiple sources
    soc_true: float = 0.0  # High precision from Service 0x21
    soc_display: float = 0.0  # Dashboard display SOC
    soc_precise: float = 0.0  # 0.1% precision (ZE0/AZE0 only)

    # State of Health (SOH) - Multiple sources
    soh: float = 0.0  # From 0x5BC broadcast
    soh_alt: float = 0.0  # From 0x5B3 byte shift method
    soh_precise: float = 0.0  # High precision from Service 0x21

    # Battery Capacity
    gids: float = 0.0  # Remaining capacity in 80Wh units
    stored_energy_gids: float = 0.0  # From 0x5B3
    ah_capacity: float = 0.0  # Amp-hour capacity
    charge_bars: float = 0.0  # Capacity bars (0-12)

    # Pack Voltage & Current
    pack_voltage: float = 0.0
    pack_current: float = 0.0  # Negative=charging, positive=discharging

    # Pack Temperature
    pack_temp_c: float = 0.0  # Average temperature
    temp_sensor_1: float = 0.0  # Individual sensor 1
    temp_sensor_2: float = 0.0  # Individual sensor 2
    temp_sensor_3: float = 0.0  # Individual sensor 3
    temp_sensor_4: float = 0.0  # Individual sensor 4

    # Cell Voltages
    cell_voltages: List[float] = field(default_factory=list)  # All 96 cells
    cell_v_min: float = 0.0  # Minimum cell voltage
    cell_v_max: float = 0.0  # Maximum cell voltage
    cell_v_delta: float = 0.0  # Voltage spread (max - min)
    cell_delta_mv: float = 0.0  # Legacy field (same as cell_v_delta)

    # Cell Balancing
    balancing_bitmap: List[int] = field(default_factory=list)  # Bitmap of balancing cells

    # Motor & Inverter
    motor_voltage: float = 0.0
    motor_torque: float = 0.0
    motor_rpm: float = 0.0
    motor_temp: float = 0.0
    igbt_temp: float = 0.0  # Inverter temperature

    # Charging
    charger_power: float = 0.0
    ac_voltage: float = 0.0
    j1772_current_limit: float = 0.0
    qc_voltage: float = 0.0

    # Range & Warnings
    range_km: float = 0.0
    low_battery_warning: float = 0.0
    critical_battery_warning: float = 0.0

    # Environmental
    outside_temp: float = 0.0

    # Diagnostics
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
