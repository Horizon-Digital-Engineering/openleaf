"""BLE-backed ELM327 transport for BLE-only adapters like LELink2."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

from .obd import (
    HANDSHAKE_COMMANDS,
    OBDTransport,
    _build_pid_request,
    _parse_isotp_lines,
)

try:  # pragma: no cover - exercised in hardware environments
    from bleak import BleakClient  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - dependency injected in tests
    BleakClient = None  # type: ignore

LOGGER = logging.getLogger(__name__)


class BleElm327Adapter:
    """BLE GATT transport that mimics the pyserial interface used by OBDTransport."""

    def __init__(
        self,
        address: str,
        service_uuid: str,
        write_char_uuid: str,
        notify_char_uuid: str,
        timeout: float,
        client_factory: Optional[Callable[[str], Any]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        run_in_thread: bool = True,
        connection_logger: Optional[logging.Logger] = None,
    ) -> None:
        if client_factory is None and BleakClient is None:
            raise ImportError("bleak is required for BLE transport support")
        self.address = address
        self.service_uuid = service_uuid
        self.write_char_uuid = write_char_uuid
        self.notify_char_uuid = notify_char_uuid
        self.timeout = timeout
        self._client_factory = client_factory or BleakClient  # type: ignore[assignment]
        self._client: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._use_thread = run_in_thread
        if self._use_thread:
            self._thread = threading.Thread(target=self._start_loop, daemon=True)
            self._thread.start()
            self._loop_ready.wait(timeout=2.0)
        else:
            self._thread = None
            self._loop_ready.set()
        self._line_queue: queue.Queue[str] = queue.Queue()
        self._rx_buffer = ""
        self._log_callback = log_callback
        self._connection_logger = connection_logger
        self._initialized = False
        self._log_conn("info", f"BLE adapter init address={address}")

    def _start_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()
        loop.run_forever()

    @property
    def is_open(self) -> bool:
        return bool(self._client and self._client.is_connected)

    def connect(self) -> None:
        self._run_coro(self._connect())
        self._initialized = False

    def close(self) -> None:
        if self._client and self._client.is_connected:
            try:
                self._run_coro(self._disconnect())
            finally:
                self._client = None
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
        self._log_conn("info", "BLE ELM327 handshake complete")

    def query_pid(self, pid) -> bytes:
        self.ensure_ready()
        self._write(f"ATSH{pid.request_id:03X}")
        self._drain_lines()
        self._write(_build_pid_request(pid))
        lines = self._drain_lines()
        return _parse_isotp_lines(lines, pid.response_id)

    def _write(self, command: str) -> None:
        payload = (command.strip() + "\r").encode("ascii")
        self._run_coro(self._async_write(payload))
        if self._log_callback:
            self._log_callback("tx", command.strip())
        self._log_conn("debug", f"tx {command.strip()}")

    def _drain_lines(self) -> List[str]:
        lines: List[str] = []
        end_time = time.time() + self.timeout
        total_length: Optional[int] = None
        payload_collected = 0
        while time.time() < end_time:
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            try:
                line = self._line_queue.get(timeout=remaining)
            except queue.Empty:
                break
            if line == ">":
                break
            if self._log_callback:
                self._log_callback("rx", line)
            self._log_conn("debug", f"rx {line}")
            lines.append(line)
            try:
                parts = line.strip().split()
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

    def _run_coro(self, coro):
        if not self._loop_ready.is_set():
            raise RuntimeError("BLE event loop not ready")
        if not self._use_thread:
            return asyncio.run(coro)
        if self._loop is None:
            raise RuntimeError("BLE event loop not ready")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result()

    async def _connect(self) -> None:
        self._client = self._client_factory(self.address)
        await self._client.connect()
        await self._client.start_notify(self.notify_char_uuid, self._on_notify)

    async def _disconnect(self) -> None:
        try:
            await self._client.stop_notify(self.notify_char_uuid)
        finally:
            await self._client.disconnect()

    async def _async_write(self, payload: bytes) -> None:
        await self._client.write_gatt_char(self.write_char_uuid, payload, response=True)

    def _on_notify(self, _: Any, data: bytearray) -> None:
        text = data.decode(errors="ignore")
        self._rx_buffer += text
        while True:
            if ">" in self._rx_buffer:
                before, self._rx_buffer = self._rx_buffer.split(">", 1)
                for segment in before.splitlines():
                    segment = segment.strip()
                    if segment:
                        self._line_queue.put_nowait(segment)
                self._line_queue.put_nowait(">")
                continue
            if "\n" in self._rx_buffer or "\r" in self._rx_buffer:
                parts = self._rx_buffer.replace("\r", "\n").split("\n")
                self._rx_buffer = parts[-1]
                for segment in parts[:-1]:
                    segment = segment.strip()
                    if segment:
                        self._line_queue.put_nowait(segment)
                continue
            break

    def _log_conn(self, level: str, msg: str) -> None:
        if not self._connection_logger:
            return
        log_fn = getattr(self._connection_logger, level, self._connection_logger.info)
        log_fn(msg)


class BleOBDTransport(OBDTransport):
    """OBD transport using BLE instead of serial."""

    def __init__(
        self,
        *,
        address: str,
        service_uuid: str,
        write_char_uuid: str,
        notify_char_uuid: str,
        timeout_sec: float,
        update_interval_sec: float,
        pid_path: str,
        reconnect_delay_sec: float = 5.0,
        client_factory: Optional[Callable[[str], Any]] = None,
        run_in_thread: bool = True,
        connection_logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(
            port="",
            baudrate=0,
            timeout_sec=timeout_sec,
            update_interval_sec=update_interval_sec,
            pid_path=pid_path,
            reconnect_delay_sec=reconnect_delay_sec,
            adapter=object(),
            connection_logger=connection_logger,
        )
        self.adapter = BleElm327Adapter(
            address=address,
            service_uuid=service_uuid,
            write_char_uuid=write_char_uuid,
            notify_char_uuid=notify_char_uuid,
            timeout=timeout_sec,
            client_factory=client_factory,
            log_callback=self._record_event,
            run_in_thread=run_in_thread,
            connection_logger=connection_logger,
        )
        self._log_transport_start(port=address, mode="ble")

    def loop(self) -> Iterable[Dict[str, Any]]:
        return self._generator()
