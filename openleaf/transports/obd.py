"""ELM327 Bluetooth OBD-II transport for the Nissan Leaf."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, Iterator, List, Optional, Sequence

import yaml

from .base import Transport

try:  # pragma: no cover - exercised in hardware environments
    import serial  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - dependency injected in tests
    serial = None  # type: ignore

LOGGER = logging.getLogger(__name__)

HANDSHAKE_COMMANDS = ("ATZ", "ATI", "ATL1", "ATH1", "ATS1", "ATAL", "ATSP6")


@dataclass(slots=True)
class PidSignal:
    """Describes how to extract and scale a single signal from a PID response."""

    key: str
    start_bit: int
    length: int
    scale: float = 1.0
    offset: float = 0.0
    enum: Optional[Dict[int, Any]] = None


@dataclass(slots=True)
class PidDefinition:
    """Request/response metadata for a Leaf PID."""

    name: str
    request_id: int
    response_id: int
    service: int
    data_identifier: int
    signals: List[PidSignal]
    poll_interval_sec: Optional[float] = None


def _parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"Unsupported int format: {value!r}")


def load_pid_definitions(path: str) -> List[PidDefinition]:
    """Load PID definitions from a YAML file."""

    pid_path = Path(path)
    if not pid_path.exists():
        raise FileNotFoundError(f"PID definition file not found: {pid_path}")

    raw = yaml.safe_load(pid_path.read_text(encoding="utf-8")) or {}
    definitions: List[PidDefinition] = []
    for entry in raw.get("leaf_pids", []):
        signals = [
            PidSignal(
                key=signal["key"],
                start_bit=int(signal["start_bit"]),
                length=int(signal["length"]),
                scale=float(signal.get("scale", 1.0)),
                offset=float(signal.get("offset", 0.0)),
                enum=signal.get("enum"),
            )
            for signal in entry.get("signals", [])
        ]
        definitions.append(
            PidDefinition(
                name=entry["name"],
                request_id=_parse_int(entry["request_id"]),
                response_id=_parse_int(entry["response_id"]),
                service=_parse_int(entry["service"]),
                data_identifier=_parse_int(entry["data_identifier"]),
                signals=signals,
                poll_interval_sec=entry.get("poll_interval_sec"),
            )
        )
    return definitions


def _build_pid_request(pid: PidDefinition) -> str:
    """Compose a request payload for the given PID."""

    if pid.data_identifier > 0xFF:
        data_id_bytes = pid.data_identifier.to_bytes(2, "big")
    else:
        data_id_bytes = pid.data_identifier.to_bytes(1, "big")
    payload: List[int] = [pid.service, *data_id_bytes]
    return " ".join(f"{byte:02X}" for byte in payload)


def _extract_bits(data: bytes, start_bit: int, length: int) -> int:
    if length <= 0:
        return 0
    end_bit = start_bit + length
    start_byte = start_bit // 8
    end_byte = (end_bit + 7) // 8
    slice_bytes = data[start_byte:end_byte]
    if not slice_bytes:
        return 0
    value = int.from_bytes(slice_bytes, "big")
    total_bits = len(slice_bytes) * 8
    shift = total_bits - length - (start_bit % 8)
    mask = (1 << length) - 1
    return (value >> shift) & mask


def _strip_response_prefix(pid: PidDefinition, payload: bytes) -> bytes:
    """Remove the service/DID echo prefix if present."""

    if not payload:
        return payload
    expected_service = pid.service | 0x40
    if payload[0] != expected_service:
        return payload
    did_bytes = pid.data_identifier.to_bytes(2 if pid.data_identifier > 0xFF else 1, "big")
    prefix_len = 1 + len(did_bytes)
    if payload[1:prefix_len] == did_bytes:
        return payload[prefix_len:]
    return payload


def _decode_signals(pid: PidDefinition, payload: bytes) -> Dict[str, Any]:
    payload = _strip_response_prefix(pid, payload)
    decoded: Dict[str, Any] = {}
    for signal in pid.signals:
        raw_value = _extract_bits(payload, signal.start_bit, signal.length)
        scaled = (raw_value * signal.scale) + signal.offset
        if signal.enum and raw_value in signal.enum:
            decoded_value = signal.enum[raw_value]
        else:
            decoded_value = scaled
        decoded[signal.key] = decoded_value
    return decoded


def _parse_isotp_lines(lines: Sequence[str], response_id: int) -> bytes:
    """Assemble ISO-TP payload bytes from ELM327 response lines."""

    payload_bytes: List[int] = []
    expected_header = f"{response_id:X}".upper()
    total_length: Optional[int] = None

    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        header = parts[0].upper()
        if header != expected_header and not header.endswith(expected_header):
            continue
        data_bytes = [int(part, 16) for part in parts[1:]]
        if not data_bytes:
            continue
        pci = data_bytes[0]
        frame_type = pci >> 4
        if frame_type == 0:  # single frame
            length = pci & 0x0F
            return bytes(data_bytes[1 : 1 + length])
        if frame_type == 1:  # first frame
            total_length = ((pci & 0x0F) << 8) | data_bytes[1]
            payload_bytes.extend(data_bytes[2:])
            continue
        if frame_type == 2:  # consecutive frame
            payload_bytes.extend(data_bytes[1:])

    if total_length is not None:
        return bytes(payload_bytes[:total_length])
    return bytes(payload_bytes)


class Elm327Adapter:
    """Thin wrapper around pyserial to speak ELM327-style AT commands."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 1.0,
        serial_factory: Optional[Callable[..., Any]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        connection_logger: Optional[logging.Logger] = None,
    ) -> None:
        if serial_factory is None and serial is None:
            raise ImportError("pyserial is required for OBD transport support")
        self._serial_factory = serial_factory or serial.Serial  # type: ignore[attr-defined]
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None
        self._initialized = False
        self._log_callback = log_callback
        self._connection_logger = connection_logger

    @property
    def is_open(self) -> bool:
        return bool(self._serial and getattr(self._serial, "is_open", False))

    def connect(self) -> None:
        self._log_connection("info", f"Opening serial port {self.port} @ {self.baudrate}")
        self._serial = self._serial_factory(self.port, baudrate=self.baudrate, timeout=self.timeout)
        self._initialized = False

    def close(self) -> None:
        if self._serial:
            try:
                self._serial.close()
            finally:
                self._serial = None
            self._initialized = False

    def ensure_ready(self) -> None:
        if not self.is_open:
            self.connect()
        if not self._initialized:
            self._initialize_adapter()

    def _initialize_adapter(self) -> None:
        for command in HANDSHAKE_COMMANDS:
            self._write(command)
            self._drain_lines()
        self._initialized = True
        self._log_connection("info", "ELM327 handshake complete")

    def query_pid(self, pid: PidDefinition) -> bytes:
        self.ensure_ready()
        self._write(f"ATSH{pid.request_id:03X}")
        self._drain_lines()
        self._write(_build_pid_request(pid))
        lines = self._drain_lines()
        return _parse_isotp_lines(lines, pid.response_id)

    def _write(self, command: str) -> None:
        if not self._serial:
            raise RuntimeError("Serial connection not open")
        payload = (command.strip() + "\r").encode("ascii")
        self._serial.write(payload)
        if self._log_callback:
            self._log_callback("tx", command.strip())

    def _drain_lines(self) -> List[str]:
        if not self._serial:
            return []
        lines: List[str] = []
        total_length: Optional[int] = None
        payload_collected = 0
        while True:
            raw = self._serial.readline()
            if not raw:
                break
            decoded = raw.decode(errors="ignore").strip()
            if not decoded:
                continue
            if decoded == ">":
                break
            if self._log_callback:
                self._log_callback("rx", decoded)
            lines.append(decoded)
            try:
                parts = decoded.strip().split()
                if not parts:
                    continue
                data_bytes = [int(part, 16) for part in parts[1:]]
                if not data_bytes:
                    continue
                pci = data_bytes[0]
                frame_type = pci >> 4
                if frame_type == 0:  # single frame
                    total_length = pci & 0x0F
                    payload_collected += len(data_bytes) - 1
                elif frame_type == 1:  # first frame
                    total_length = ((pci & 0x0F) << 8) | data_bytes[1]
                    payload_collected += len(data_bytes) - 2
                elif frame_type == 2:  # consecutive frame
                    payload_collected += len(data_bytes) - 1
                if total_length is not None and payload_collected >= total_length:
                    break
            except Exception:
                continue
        return lines

    def _log_connection(self, level: str, msg: str) -> None:
        if not self._connection_logger:
            return
        log_fn = getattr(self._connection_logger, level, self._connection_logger.info)
        log_fn(msg)


class OBDTransport(Transport):
    """Bluetooth OBD transport backed by an ELM327 adapter."""

    def __init__(
        self,
        *,
        port: str,
        baudrate: int,
        timeout_sec: float,
        update_interval_sec: float,
        pid_path: str,
        reconnect_delay_sec: float = 5.0,
        serial_factory: Optional[Callable[..., Any]] = None,
        adapter: Optional[Any] = None,
        connection_logger: Optional[logging.Logger] = None,
    ) -> None:
        self.update_interval_sec = update_interval_sec
        self.reconnect_delay_sec = reconnect_delay_sec
        self.pid_definitions = load_pid_definitions(pid_path)
        self._log: Deque[Dict[str, Any]] = deque(maxlen=200)
        if adapter is None:
            self.adapter = Elm327Adapter(
                port=port,
                baudrate=baudrate,
                timeout=timeout_sec,
                serial_factory=serial_factory,
                log_callback=self._record_event,
                connection_logger=connection_logger,
            )
        else:
            self.adapter = adapter
        self._connection_logger = connection_logger
        self._trace_files = self._derive_trace_files(port, connection_logger)
        self._last_polled: Dict[str, float] = {}
        self._log_transport_start(port=port, mode="obd")

    def loop(self) -> Iterable[Dict[str, Any]]:
        return self._generator()

    def _generator(self) -> Iterator[Dict[str, Any]]:
        while True:
            try:
                update = self._poll_all()
                if update:
                    yield update
                time.sleep(self.update_interval_sec)
            except Exception as exc:  # pragma: no cover - protective loop
                LOGGER.warning("OBD transport error: %s. Attempting reconnect.", exc)
                self.adapter.close()
                time.sleep(self.reconnect_delay_sec)

    def _poll_all(self) -> Dict[str, Any]:
        self.adapter.ensure_ready()
        aggregated: Dict[str, Any] = {}
        now = time.time()
        for pid in self.pid_definitions:
            interval = pid.poll_interval_sec or self.update_interval_sec
            last = self._last_polled.get(pid.name)
            if last is not None and (now - last) < interval:
                continue
            payload = self.adapter.query_pid(pid)
            if not payload:
                continue
            decoded = _decode_signals(pid, payload)
            aggregated.update(decoded)
            self._last_polled[pid.name] = now
        return aggregated

    def _record_event(self, direction: str, data: str) -> None:
        self._log.append({"ts": time.time(), "direction": direction, "data": data})
        if self._connection_logger:
            self._connection_logger.debug("%s %s", direction, data)
            self._connection_logger.info("%s %s", direction, data)
        logging.getLogger("openleaf.transport").debug("%s %s", direction, data)
        logging.getLogger("openleaf.transport").info("%s %s", direction, data)
        self._write_traces(direction, data)

    def _log_transport_start(self, *, port: str, mode: str) -> None:
        msg = f"Transport start mode={mode} target={port}"
        if self._connection_logger:
            self._connection_logger.info(msg)
        logging.getLogger("openleaf.transport").info(msg)
        self._write_traces("info", msg)

    def _derive_trace_files(self, port: str, logger: Optional[logging.Logger]) -> list[Path]:
        traces: list[Path] = []
        try:
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            base = "obd"
            if logger and logger.name:
                base = logger.name.split(".")[-1] or base
            elif port:
                base = f"obd_{Path(port).name}"
            traces.append(log_dir / "obd_trace.log")
            traces.append(log_dir / f"{base}.trace.log")
        except Exception:
            return []
        return traces

    def _write_traces(self, direction: str, data: str) -> None:
        if not getattr(self, "_trace_files", None):
            return
        line = f"{direction} {data}\n"
        for path in self._trace_files:
            try:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
            except Exception:
                continue

    def debug_log(self) -> list[Dict[str, Any]]:
        return list(self._log)
