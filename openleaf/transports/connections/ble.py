"""BLE connection for ELM327 adapters."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from typing import Any, List, Optional

from .base import OBDConnection

try:
    from bleak import BleakClient  # type: ignore
except ImportError:
    BleakClient = None  # type: ignore

LOGGER = logging.getLogger(__name__)


class BLEConnection(OBDConnection):
    """BLE connection for ELM327 adapters like LELink2, Vgate iCar, OBDLink LX."""

    def __init__(
        self,
        address: str,
        service_uuid: str = "0000ffe0-0000-1000-8000-00805f9b34fb",
        write_char_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb",
        notify_char_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb",
        timeout: float = 1.0,
    ):
        """Initialize BLE connection.

        Args:
            address: BLE MAC address or UUID of the adapter
            service_uuid: GATT service UUID (standard for most BLE ELM327)
            write_char_uuid: Characteristic UUID for writing commands
            notify_char_uuid: Characteristic UUID for notifications
            timeout: Connection timeout in seconds
        """
        if BleakClient is None:
            raise ImportError("bleak is required for BLE support: pip install bleak")

        self.address = address
        self.service_uuid = service_uuid
        self.write_char_uuid = write_char_uuid
        self.notify_char_uuid = notify_char_uuid
        self.timeout = timeout

        self._client: Optional[BleakClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._loop_ready = threading.Event()
        self._line_queue: queue.Queue[str] = queue.Queue()
        self._rx_buffer = ""

        # Start async event loop in background thread
        self._start_event_loop()

    def _start_event_loop(self) -> None:
        """Start asyncio event loop in background thread."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._loop_ready.wait(timeout=2.0):
            raise RuntimeError("Failed to start async event loop")

    def _run_loop(self) -> None:
        """Run the asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._loop.run_forever()

    def _run_async(self, coro) -> Any:
        """Run async coroutine in the background loop."""
        if not self._loop:
            raise RuntimeError("Event loop not started")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=self.timeout * 2)

    def connect_sync(self) -> None:
        """Connect to BLE adapter."""
        LOGGER.info(f"Connecting to BLE adapter at {self.address}")
        self._run_async(self._connect())
        LOGGER.info(f"Connected to {self.address}")

    async def _connect(self) -> None:
        """Async connect implementation."""
        self._client = BleakClient(self.address)
        await self._client.connect()

        # Setup notification handler
        await self._client.start_notify(
            self.notify_char_uuid,
            self._notification_handler
        )

    def disconnect_sync(self) -> None:
        """Disconnect from BLE adapter."""
        if self._client:
            self._run_async(self._disconnect())
            self._client = None
        LOGGER.info(f"Disconnected from {self.address}")

    async def _disconnect(self) -> None:
        """Async disconnect implementation."""
        if self._client and self._client.is_connected:
            await self._client.stop_notify(self.notify_char_uuid)
            await self._client.disconnect()

    def send_sync(self, command: str) -> None:
        """Send command to adapter."""
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to BLE adapter")

        # ELM327 expects commands terminated with \r
        if not command.endswith('\r'):
            command += '\r'

        self._run_async(self._send(command))
        LOGGER.debug(f"Sent: {command.strip()}")

    async def _send(self, command: str) -> None:
        """Async send implementation."""
        data = command.encode('ascii')
        await self._client.write_gatt_char(self.write_char_uuid, data, response=False)

    def receive_sync(self, timeout: Optional[float] = None) -> str:
        """Receive response from adapter until '>' prompt.

        Args:
            timeout: Maximum time to wait for complete response

        Returns:
            Response lines joined with newlines
        """
        timeout = timeout or self.timeout
        lines: List[str] = []

        # Track ISO-TP payload for early termination
        total_length: Optional[int] = None
        payload_collected = 0

        end_time = time.time() + timeout
        while time.time() < end_time:
            remaining = end_time - time.time()
            if remaining <= 0:
                break

            try:
                line = self._line_queue.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                continue

            # '>' indicates end of response
            if line == '>':
                break

            lines.append(line)
            LOGGER.debug(f"Received: {line}")

            # Check for ISO-TP frame info to optimize reading
            try:
                parts = line.split()
                if len(parts) > 1:
                    data_bytes = [int(part, 16) for part in parts[1:]]
                    if data_bytes:
                        pci = data_bytes[0]
                        frame_type = pci >> 4

                        if frame_type == 0:  # Single frame
                            total_length = pci & 0x0F
                            payload_collected += len(data_bytes) - 1
                        elif frame_type == 1:  # First frame
                            total_length = ((pci & 0x0F) << 8) | data_bytes[1]
                            payload_collected += len(data_bytes) - 2
                        elif frame_type == 2:  # Consecutive frame
                            payload_collected += len(data_bytes) - 1

                        # If we've collected all expected data, stop waiting
                        if total_length and payload_collected >= total_length:
                            # Try to get prompt quickly
                            try:
                                prompt = self._line_queue.get(timeout=0.1)
                                if prompt and prompt != '>':
                                    lines.append(prompt)
                            except queue.Empty:
                                pass
                            break
            except (ValueError, IndexError):
                pass  # Not a valid frame, continue reading

        return '\n'.join(lines)

    def is_connected(self) -> bool:
        """Check if connected to adapter."""
        return bool(self._client and self._client.is_connected)

    def _notification_handler(self, sender: Any, data: bytearray) -> None:
        """Handle BLE notifications from adapter."""
        # Decode and buffer the data
        text = data.decode('ascii', errors='ignore')
        self._rx_buffer += text

        # Split by line terminators and queue complete lines
        while '\r' in self._rx_buffer:
            line, self._rx_buffer = self._rx_buffer.split('\r', 1)
            line = line.strip()
            if line or line == '>':  # Include empty prompt
                self._line_queue.put(line)