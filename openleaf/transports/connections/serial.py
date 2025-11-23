"""Serial connection for ELM327 adapters."""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from .base import OBDConnection

try:
    import serial  # type: ignore
    import serial.tools.list_ports  # type: ignore
except ImportError:
    serial = None  # type: ignore

LOGGER = logging.getLogger(__name__)


class SerialConnection(OBDConnection):
    """Serial connection for USB or Bluetooth Classic ELM327 adapters."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 1.0,
    ):
        """Initialize serial connection.

        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0', '/dev/rfcomm0', 'COM3')
            baudrate: Serial baudrate (usually 115200 for ELM327)
            timeout: Read timeout in seconds
        """
        if serial is None:
            raise ImportError("pyserial is required for serial support: pip install pyserial")

        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Optional[serial.Serial] = None

    def connect_sync(self) -> None:
        """Connect to serial adapter."""
        LOGGER.info(f"Connecting to serial adapter at {self.port} ({self.baudrate} baud)")
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.timeout,
        )
        # Give adapter time to initialize
        time.sleep(0.5)
        LOGGER.info(f"Connected to {self.port}")

    def disconnect_sync(self) -> None:
        """Disconnect from serial adapter."""
        if self._serial:
            if self._serial.is_open:
                self._serial.close()
            self._serial = None
        LOGGER.info(f"Disconnected from {self.port}")

    def send_sync(self, command: str) -> None:
        """Send command to adapter."""
        if not self._serial or not self._serial.is_open:
            raise ConnectionError("Not connected to serial adapter")

        # ELM327 expects commands terminated with \r
        if not command.endswith('\r'):
            command += '\r'

        self._serial.write(command.encode('ascii'))
        self._serial.flush()
        LOGGER.debug(f"Sent: {command.strip()}")

    def receive_sync(self, timeout: Optional[float] = None) -> str:
        """Receive response from adapter until '>' prompt.

        Args:
            timeout: Maximum time to wait for complete response

        Returns:
            Response lines joined with newlines
        """
        if not self._serial or not self._serial.is_open:
            raise ConnectionError("Not connected to serial adapter")

        timeout = timeout or self.timeout
        old_timeout = self._serial.timeout
        self._serial.timeout = timeout

        lines: List[str] = []
        # Track ISO-TP payload for early termination
        total_length: Optional[int] = None
        payload_collected = 0

        try:
            end_time = time.time() + timeout
            while time.time() < end_time:
                remaining = end_time - time.time()
                if remaining <= 0:
                    break

                self._serial.timeout = min(remaining, 0.1)
                line = self._serial.readline()
                if not line:
                    continue

                decoded = line.decode('ascii', errors='ignore').strip()
                if not decoded:
                    continue

                # '>' indicates end of response
                if decoded == '>':
                    break

                lines.append(decoded)
                LOGGER.debug(f"Received: {decoded}")

                # Check for ISO-TP frame info to optimize reading
                try:
                    parts = decoded.split()
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
                                # Read one more line for potential prompt
                                prompt = self._serial.readline()
                                if prompt and prompt.strip() != b'>':
                                    lines.append(prompt.decode('ascii', errors='ignore').strip())
                                break
                except (ValueError, IndexError):
                    pass  # Not a valid frame, continue reading

        finally:
            self._serial.timeout = old_timeout

        return '\n'.join(lines)

    def is_connected(self) -> bool:
        """Check if connected to adapter."""
        return bool(self._serial and self._serial.is_open)

    @staticmethod
    def list_ports() -> list[str]:
        """List available serial ports.

        Returns:
            List of available port names
        """
        if serial is None:
            return []

        ports = []
        for port_info in serial.tools.list_ports.comports():
            ports.append(port_info.device)
            LOGGER.debug(f"Found port: {port_info.device} - {port_info.description}")

        return ports