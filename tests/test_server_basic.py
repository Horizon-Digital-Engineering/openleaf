from __future__ import annotations

import time

from fastapi.testclient import TestClient

from openleaf.config import AppConfig, LoggingConfig, TransportConfig, VehicleConfig
from openleaf.server import LeafStateServer


def create_server() -> LeafStateServer:
    config = AppConfig(
        transport=TransportConfig(type="synthetic", update_interval_sec=0.0),
        logging=LoggingConfig(),
        vehicle=VehicleConfig(cell_count=4),
    )
    server = LeafStateServer(config)
    server.start_background_loop()
    time.sleep(0.05)
    return server


def test_health_endpoint() -> None:
    server = create_server()
    client = TestClient(server.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_state_endpoint_has_leaf_fields() -> None:
    server = create_server()
    client = TestClient(server.app)
    response = client.get("/state")
    assert response.status_code == 200
    data = response.json()
    assert "soc_true" in data
    assert "pack_voltage" in data
    assert "cell_voltages" in data
    assert len(data["cell_voltages"]) == 4
    assert "dtcs" in data
