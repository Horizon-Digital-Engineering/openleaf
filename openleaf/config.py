"""Configuration loading utilities for OpenLeaf."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict, Literal, Type, TypeVar

import yaml

__all__ = [
    "TransportConfig",
    "LoggingConfig",
    "VehicleConfig",
    "AppConfig",
    "load_config",
]


@dataclass(slots=True)
class TransportConfig:
    """Transport-related configuration."""

    type: Literal["synthetic", "obd", "ble", "can", "playback"] = "synthetic"
    update_interval_sec: float = 0.5
    serial_port: str = "/dev/rfcomm0"
    baudrate: int = 115200
    timeout_sec: float = 1.0
    pid_path: str = "pids/leaf.yaml"
    reconnect_delay_sec: float = 5.0
    enable_flow_control: bool = True
    ble_address: str = ""
    ble_service_uuid: str = "0000ffe0-0000-1000-8000-00805f9b34fb"
    ble_write_char_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb"
    ble_notify_char_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb"


@dataclass(slots=True)
class LoggingConfig:
    """Logging configuration placeholders for future recorder support."""

    enabled: bool = False
    path: str = "./logs"
    level: str = "INFO"


@dataclass(slots=True)
class VehicleConfig:
    """Metadata describing the specific Leaf variant in use."""

    year: int = 2013
    generation: str = "ZE0"
    model: str = "SV"
    pack_kwh: float = 24.0
    cell_count: int = 96


@dataclass(slots=True)
class AppConfig:
    """Root configuration for the OpenLeaf application."""

    transport: TransportConfig
    logging: LoggingConfig
    vehicle: VehicleConfig


T = TypeVar("T")


def _instantiate_dataclass(cls: Type[T], data: Dict[str, Any] | None) -> T:
    allowed_fields = {field.name for field in fields(cls)}
    filtered: Dict[str, Any] = {}
    if data:
        filtered = {key: value for key, value in data.items() if key in allowed_fields}
    return cls(**filtered)  # type: ignore[arg-type]


def load_config(path: str = "config.yaml") -> AppConfig:
    """Load YAML configuration into structured dataclasses.

    Args:
        path: Path to the YAML configuration file.

    Raises:
        FileNotFoundError: If the configuration file does not exist.

    Returns:
        An AppConfig instance populated with defaults for missing keys.
    """

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    raw: Dict[str, Any] = {}
    content = config_path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(content)
    if isinstance(loaded, dict):
        raw = loaded

    transport_cfg = _instantiate_dataclass(
        TransportConfig, raw.get("transport") if isinstance(raw.get("transport"), dict) else None
    )
    logging_cfg = _instantiate_dataclass(
        LoggingConfig, raw.get("logging") if isinstance(raw.get("logging"), dict) else None
    )
    vehicle_cfg = _instantiate_dataclass(
        VehicleConfig, raw.get("vehicle") if isinstance(raw.get("vehicle"), dict) else None
    )
    return AppConfig(transport=transport_cfg, logging=logging_cfg, vehicle=vehicle_cfg)
