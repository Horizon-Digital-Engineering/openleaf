from __future__ import annotations

import textwrap

import pytest

from openleaf.config import AppConfig, LoggingConfig, TransportConfig, VehicleConfig, load_config


def test_load_config_missing_file(tmp_path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        load_config(str(missing))


def test_load_config_partial_defaults(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        textwrap.dedent(
            """
            transport:
              update_interval_sec: 1.5
            """
        ),
        encoding="utf-8",
    )

    config = load_config(str(cfg_path))
    assert config.transport.type == "synthetic"
    assert config.transport.update_interval_sec == 1.5
    assert config.logging == LoggingConfig()
    assert config.vehicle == VehicleConfig()


def test_load_config_full_override(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        textwrap.dedent(
            """
            transport:
              type: can
              update_interval_sec: 0.2
            logging:
              enabled: true
              path: /tmp/leaf.log
            vehicle:
              year: 2020
              generation: ZE1
              model: SL Plus
              pack_kwh: 62
              cell_count: 96
            """
        ),
        encoding="utf-8",
    )

    config = load_config(str(cfg_path))
    assert isinstance(config, AppConfig)
    assert config.transport == TransportConfig(type="can", update_interval_sec=0.2)
    assert config.logging == LoggingConfig(enabled=True, path="/tmp/leaf.log", level="INFO")
    assert config.vehicle == VehicleConfig(
        year=2020, generation="ZE1", model="SL Plus", pack_kwh=62.0, cell_count=96
    )
