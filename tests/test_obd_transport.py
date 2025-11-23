from __future__ import annotations

import textwrap
from pathlib import Path

from openleaf.transports.obd import HANDSHAKE_COMMANDS, OBDTransport


class FakeSerial:
    """Minimal pyserial stand-in for exercising the OBD transport."""

    def __init__(self, *, response_map: dict[str, list[str]]) -> None:
        self.response_map = response_map
        self.written: list[str] = []
        self._buffer: list[str] = []
        self.is_open = True

    def write(self, payload: bytes) -> None:
        command = payload.decode().strip()
        self.written.append(command)
        responses = self.response_map.get(command, ["OK"])
        self._buffer.extend(responses + [">"])

    def readline(self) -> bytes:
        if not self._buffer:
            return b""
        return (self._buffer.pop(0) + "\r").encode()

    def close(self) -> None:
        self.is_open = False


def test_obd_transport_multiframe_decode(tmp_path: Path) -> None:
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
                  - key: "pack_voltage"
                    start_bit: 16
                    length: 16
                    scale: 0.01
                  - key: "pack_temp_c"
                    start_bit: 32
                    length: 8
                    scale: 1.0
                    offset: -40
                  - key: "cell_delta_mv"
                    start_bit: 40
                    length: 8
                    scale: 1.0
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

    response_map = {command: ["OK"] for command in HANDSHAKE_COMMANDS}
    response_map["ATSH79B"] = ["OK"]
    response_map["21 01"] = [
        "7BB 10 0A 61 01 01 F4 8C A0",
        "7BB 21 46 05 11 22",
    ]
    response_map["21 61"] = ["7BB 04 61 61 03 98"]
    fake_serial = FakeSerial(response_map=response_map)

    def serial_factory(*_: object, **__: object) -> FakeSerial:
        return fake_serial

    transport = OBDTransport(
        port="/dev/rfcomm0",
        baudrate=115200,
        timeout_sec=1.0,
        update_interval_sec=0.0,
        pid_path=str(pid_path),
        reconnect_delay_sec=0.1,
        serial_factory=serial_factory,
    )

    iterator = iter(transport.loop())
    update = next(iterator)

    assert update["soc_true"] == 50.0
    assert update["pack_voltage"] == 360.0
    assert update["pack_temp_c"] == 30.0
    assert update["cell_delta_mv"] == 5.0
    assert update["soh"] == 92.0

    # Ensure handshake and headers were issued.
    for command in HANDSHAKE_COMMANDS:
        assert command in fake_serial.written
    assert "ATSH79B" in fake_serial.written
    assert "21 01" in fake_serial.written
    assert "21 61" in fake_serial.written

    log = transport.debug_log()
    assert any(entry["direction"] == "tx" for entry in log)
    assert any(entry["direction"] == "rx" for entry in log)
