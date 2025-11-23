from __future__ import annotations

import textwrap
from pathlib import Path

from openleaf.transports.ble import BleOBDTransport
from openleaf.transports.obd import HANDSHAKE_COMMANDS


class FakeBleakClient:
    """Minimal fake BLE client to simulate an ELM327-like GATT UART."""

    def __init__(self, responses: dict[str, list[str]]) -> None:
        self.responses = responses
        self.is_connected = False
        self.written: list[str] = []
        self._notify_cb = None

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def start_notify(self, _: str, callback) -> None:
        self._notify_cb = callback

    async def stop_notify(self, _: str) -> None:
        self._notify_cb = None

    async def write_gatt_char(self, _: str, data: bytes, response: bool = True) -> None:
        command = data.decode().strip()
        self.written.append(command)
        responses = self.responses.get(command, ["OK", ">"])
        for line in responses:
            if self._notify_cb:
                self._notify_cb(None, line.encode())


def test_ble_transport_basic_flow(tmp_path: Path) -> None:
    pid_path = tmp_path / "leaf.yaml"
    pid_path.write_text(
        textwrap.dedent(
            """
            leaf_pids:
              - name: "Battery Status Frame"
                request_id: 0x79B
                response_id: 0x7BB
                service: 0x21
                data_identifier: 0x01
                signals:
                  - key: "soc_true"
                    start_bit: 0
                    length: 16
                    scale: 0.1
              - name: "Battery SOH"
                request_id: 0x79B
                response_id: 0x7BB
                service: 0x21
                data_identifier: 0x61
                signals:
                  - key: "soh"
                    start_bit: 0
                    length: 16
                    scale: 0.1
            """
        ),
        encoding="utf-8",
    )

    response_map = {command: ["OK", ">"] for command in HANDSHAKE_COMMANDS}
    response_map["ATSH79B"] = ["OK", ">"]
    response_map["21 01"] = ["7BB 04 61 01 01 F4", ">"]
    response_map["21 61"] = ["7BB 04 61 61 03 98", ">"]

    def client_factory(address: str) -> FakeBleakClient:
        return FakeBleakClient(response_map)

    transport = BleOBDTransport(
        address="00:11:22:33:44:55",
        service_uuid="ffe0",
        write_char_uuid="ffe1",
        notify_char_uuid="ffe1",
        timeout_sec=0.1,
        update_interval_sec=0.0,
        pid_path=str(pid_path),
        reconnect_delay_sec=0.05,
        client_factory=client_factory,
        run_in_thread=False,
    )

    update = transport._poll_all()  # type: ignore[attr-defined]

    assert update["soc_true"] == 50.0
    assert update["soh"] == 92.0

    # Handshake and PID requests should be logged and written.
    client = transport.adapter._client  # type: ignore[attr-defined]
    for command in HANDSHAKE_COMMANDS:
        assert command in client.written
    assert "ATSH79B" in client.written
    assert "21 01" in client.written
    assert "21 61" in client.written

    log = transport.debug_log()
    assert any(entry["direction"] == "tx" for entry in log)
    assert any(entry["direction"] == "rx" for entry in log)
