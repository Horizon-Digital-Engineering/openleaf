"""ELM327 protocol handler - shared logic for all OBD2 connections."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

LOGGER = logging.getLogger(__name__)

# Standard ELM327 initialization commands
HANDSHAKE_COMMANDS = [
    "ATZ",    # Reset
    "ATI",    # Identify
    "ATL1",   # Linefeeds on
    "ATH1",   # Headers on
    "ATS1",   # Spaces on
    "ATAL",   # Allow long messages
    "ATSP6",  # Set protocol to ISO 15765-4 CAN (11 bit ID, 500 kbaud)
]


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


class ELM327Protocol:
    """Handles ELM327 protocol logic independent of connection type."""

    def __init__(self, connection, logger: Optional[logging.Logger] = None):
        """Initialize protocol handler.

        Args:
            connection: Connection object (BLE, Serial, or Bluetooth Classic)
            logger: Optional logger for protocol events
        """
        self.connection = connection
        self.logger = logger or LOGGER
        self.initialized = False

    def initialize(self) -> None:
        """Send ELM327 initialization commands."""
        if self.initialized:
            return

        self.logger.info("Initializing ELM327 adapter")
        for command in HANDSHAKE_COMMANDS:
            response = self.send_command(command)
            self.logger.debug(f"  {command} -> {response[:50] if response else 'no response'}...")

        self.initialized = True
        self.logger.info("ELM327 handshake complete")

    def send_command(self, command: str) -> str:
        """Send command and wait for response.

        Args:
            command: AT command or OBD2 request

        Returns:
            Response string from adapter
        """
        self.connection.send_sync(command)
        return self.connection.receive_sync()

    def query_pid(self, pid: PidDefinition) -> bytes:
        """Query a PID and return the response payload.

        Args:
            pid: PID definition with request/response info

        Returns:
            Decoded response bytes
        """
        # Ensure connection is ready
        if not self.connection.is_connected():
            self.connection.connect_sync()

        if not self.initialized:
            self.initialize()

        # Set the CAN header for this PID
        self.send_command(f"ATSH{pid.request_id:03X}")

        # Build and send the request
        request = self._build_pid_request(pid)
        response = self.send_command(request)

        # Parse the response
        lines = response.strip().split('\n') if response else []
        return self._parse_isotp_response(lines, pid.response_id)

    def _build_pid_request(self, pid: PidDefinition) -> str:
        """Build OBD2 request string for a PID.

        Args:
            pid: PID definition

        Returns:
            Hex string request (e.g., "21 01" for service 0x21, PID 0x01)
        """
        if pid.data_identifier > 0xFF:
            data_id_bytes = pid.data_identifier.to_bytes(2, "big")
        else:
            data_id_bytes = pid.data_identifier.to_bytes(1, "big")

        payload = [pid.service, *data_id_bytes]
        return " ".join(f"{byte:02X}" for byte in payload)

    def _parse_isotp_response(self, lines: Sequence[str], response_id: int) -> bytes:
        """Parse ISO-TP response frames into payload bytes.

        Args:
            lines: Response lines from ELM327
            response_id: Expected CAN ID in response

        Returns:
            Assembled payload bytes
        """
        payload_bytes: List[int] = []
        expected_header = f"{response_id:X}".upper()
        total_length: Optional[int] = None

        for line in lines:
            parts = line.strip().split()
            if not parts:
                continue

            # Check if this line has the expected header
            header = parts[0].upper()
            if header != expected_header and not header.endswith(expected_header):
                continue

            # Extract data bytes (skip the header)
            data_bytes = [int(part, 16) for part in parts[1:]]
            if not data_bytes:
                continue

            # Parse ISO-TP Protocol Control Information (PCI)
            pci = data_bytes[0]
            frame_type = pci >> 4

            if frame_type == 0:  # Single frame
                length = pci & 0x0F
                return bytes(data_bytes[1 : 1 + length])

            elif frame_type == 1:  # First frame
                total_length = ((pci & 0x0F) << 8) | data_bytes[1]
                payload_bytes.extend(data_bytes[2:])

            elif frame_type == 2:  # Consecutive frame
                payload_bytes.extend(data_bytes[1:])

        # Return assembled payload (trimmed to expected length if known)
        if total_length is not None:
            return bytes(payload_bytes[:total_length])
        return bytes(payload_bytes)

    @staticmethod
    def parse_isotp_frame_info(pci_byte: int, data_bytes: List[int]) -> tuple[int, Optional[int], int]:
        """Extract ISO-TP frame metadata.

        Args:
            pci_byte: Protocol Control Information byte
            data_bytes: All data bytes from frame

        Returns:
            Tuple of (frame_type, total_length, payload_size)
        """
        frame_type = pci_byte >> 4

        if frame_type == 0:  # Single frame
            return 0, pci_byte & 0x0F, len(data_bytes) - 1

        elif frame_type == 1:  # First frame
            length = ((pci_byte & 0x0F) << 8) | data_bytes[1]
            return 1, length, len(data_bytes) - 2

        elif frame_type == 2:  # Consecutive frame
            return 2, None, len(data_bytes) - 1

        else:
            return frame_type, None, 0


def decode_pid_response(response_bytes: bytes, pid: PidDefinition) -> Dict[str, Any]:
    """Decode a PID response into signal values.

    Args:
        response_bytes: Raw response payload
        pid: PID definition with signal info

    Returns:
        Dictionary of signal key -> decoded value
    """
    # Strip response prefix if present
    if len(response_bytes) >= 3:
        expected_prefix = bytes([pid.service + 0x40,
                                *pid.data_identifier.to_bytes(2, "big")[:2]])
        if response_bytes.startswith(expected_prefix[:2]):
            response_bytes = response_bytes[len(expected_prefix):]

    result = {}
    for signal in pid.signals:
        # Extract bits
        start_byte = signal.start_bit // 8
        end_byte = (signal.start_bit + signal.length - 1) // 8

        if end_byte >= len(response_bytes):
            continue

        # Extract and combine bytes
        value = 0
        for byte_idx in range(start_byte, end_byte + 1):
            byte_val = response_bytes[byte_idx]

            if byte_idx == start_byte:
                # Mask off upper bits we don't need
                bit_offset = signal.start_bit % 8
                mask = (1 << (8 - bit_offset)) - 1
                byte_val &= mask

            if byte_idx == end_byte:
                # Mask off lower bits we don't need
                bits_in_last_byte = (signal.start_bit + signal.length) % 8
                if bits_in_last_byte > 0:
                    shift = 8 - bits_in_last_byte
                    byte_val >>= shift

            # Add this byte's contribution
            bytes_from_end = end_byte - byte_idx
            value |= byte_val << (8 * bytes_from_end)

        # Apply scaling and offset
        if signal.enum:
            result[signal.key] = signal.enum.get(value, value)
        else:
            result[signal.key] = value * signal.scale + signal.offset

    return result