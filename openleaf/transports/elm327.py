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
    "ATL0",   # Linefeeds off (reduces data for BLE)
    "ATS0",   # Spaces off (reduces data for BLE)
    "ATH1",   # Headers on
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
    encoding: Optional[str] = None  # "array_u16_be" for cell voltage arrays
    signed: bool = False
    formula: Optional[str] = None  # e.g., "value >> 1" for bit shifts


@dataclass(slots=True)
class BroadcastFrame:
    """Definition for a passive CAN broadcast message."""

    can_id: int
    name: str
    signals: List[PidSignal]


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

        # Configure flow control for multi-frame responses
        # ATFCSH: Set flow control header (where we send FC frames TO)
        # ATFCSD: Set flow control data (30=CTS, 00=block size, 00=sep time)
        # ATFCSM1: Enable user-defined flow control mode
        self.send_command(f"ATFCSH{pid.request_id:03X}")
        self.send_command("ATFCSD300000")
        self.send_command("ATFCSM1")

        # Set the CAN header for this PID request
        self.send_command(f"ATSH{pid.request_id:03X}")

        # Build and send the request
        request = self._build_pid_request(pid)
        response = self.send_command(request)

        # Parse response (flow control is automatic now)
        lines = response.strip().split('\n') if response else []
        return self._parse_isotp_response(lines, pid.response_id)

    def monitor_broadcast(self, can_ids: List[int], duration_sec: float = 2.0) -> Dict[int, bytes]:
        """Monitor CAN bus for broadcast messages (passive sniffing).

        Uses ATCRA to filter specific CAN IDs, then ATMA to capture traffic.
        This is more reliable than monitoring all traffic on cheap adapters.

        Args:
            can_ids: List of CAN IDs to watch for (e.g., [0x5BC, 0x5B3, 0x55B])
            duration_sec: How long to monitor

        Returns:
            Dict mapping CAN ID to last received frame data
        """
        if not self.connection.is_connected():
            self.connection.connect_sync()

        if not self.initialized:
            self.initialize()

        results: Dict[int, bytes] = {}

        # Monitor each CAN ID separately with filter (more reliable)
        for can_id in can_ids:
            try:
                self.send_command("ATCAF0")  # Raw frames
                self.send_command(f"ATCRA{can_id:03X}")  # Filter to this ID only

                self.connection.send_sync("ATMA")

                import time
                start = time.time()
                per_id_time = min(duration_sec / len(can_ids), 0.5)

                while time.time() - start < per_id_time:
                    try:
                        chunk = self.connection.receive_sync(timeout=0.2)
                        if chunk:
                            for line in chunk.split():
                                line = line.strip()
                                if line.startswith(f"{can_id:03X}") and len(line) >= 5:
                                    hex_data = line[3:]
                                    if len(hex_data) >= 2:
                                        data = bytes([int(hex_data[i:i+2], 16)
                                                     for i in range(0, min(len(hex_data), 16), 2)])
                                        results[can_id] = data
                                        break  # Got one frame, move to next ID
                            if can_id in results:
                                break
                    except Exception:
                        pass

                # Stop monitoring
                self.connection.send_sync("")

            except Exception:
                pass

        # Reset filters and restore normal mode
        try:
            self.send_command("ATAR")  # Reset CAN filters
            self.send_command("ATCAF1")  # Re-enable CAN formatting
        except Exception:
            pass

        return results

    def read_dtcs(self, ecu_id: int = 0x7E4) -> List[str]:
        """Read Diagnostic Trouble Codes from an ECU using UDS Service 0x19.

        Args:
            ecu_id: ECU request ID (default 0x7E4 for Leaf battery, 0x797 for VCM)

        Returns:
            List of DTC codes as strings (e.g., ["P0A80", "U1000"])
        """
        if not self.connection.is_connected():
            self.connection.connect_sync()

        if not self.initialized:
            self.initialize()

        response_id = ecu_id + 8  # Response ID is typically request + 8

        # Set up for this ECU
        self.send_command(f"ATFCSH{ecu_id:03X}")
        self.send_command("ATFCSD300000")
        self.send_command("ATFCSM1")
        self.send_command(f"ATSH{ecu_id:03X}")

        # UDS Service 0x19 sub-function 0x02: reportDTCByStatusMask
        # 0xFF = all DTCs (confirmed, pending, etc.)
        response = self.send_command("19 02 FF")

        if not response:
            return []

        lines = response.strip().split('\n')
        payload = self._parse_isotp_response(lines, response_id)

        return self._decode_dtcs(payload)

    def _decode_dtcs(self, payload: bytes) -> List[str]:
        """Decode DTC bytes into human-readable codes.

        UDS response format for Service 0x19 sub 0x02:
        - Byte 0: 0x59 (positive response)
        - Byte 1: 0x02 (sub-function echo)
        - Byte 2: Availability status mask
        - Bytes 3+: DTC records (3 bytes DTC + 1 byte status each)

        DTC encoding (ISO 15031-6):
        - First 2 bits = type: 00=P, 01=C, 10=B, 11=U
        - Next 14 bits = 4 hex digits
        """
        dtcs = []

        if len(payload) < 3:
            return dtcs

        # Check for positive response (0x59)
        if payload[0] != 0x59:
            LOGGER.debug(f"DTC read failed, response: {payload.hex()}")
            return dtcs

        # Skip header (0x59 0x02 status_mask)
        dtc_data = payload[3:]

        # Each DTC is 4 bytes: 3 bytes DTC code + 1 byte status
        for i in range(0, len(dtc_data) - 3, 4):
            dtc_bytes = dtc_data[i:i+3]

            # Decode DTC type from first 2 bits
            type_code = (dtc_bytes[0] >> 6) & 0x03
            type_char = ['P', 'C', 'B', 'U'][type_code]

            # Remaining 14 bits form the 4-digit code
            code_value = ((dtc_bytes[0] & 0x3F) << 8) | dtc_bytes[1]
            sub_code = dtc_bytes[2]

            # Format as standard DTC (e.g., P0A80)
            dtc = f"{type_char}{code_value:04X}"
            if sub_code != 0:
                dtc += f"-{sub_code:02X}"

            dtcs.append(dtc)

        return dtcs

    def clear_dtcs(self, ecu_id: int = 0x7E4) -> bool:
        """Clear Diagnostic Trouble Codes using UDS Service 0x14.

        Args:
            ecu_id: ECU request ID

        Returns:
            True if successful
        """
        if not self.connection.is_connected():
            self.connection.connect_sync()

        if not self.initialized:
            self.initialize()

        response_id = ecu_id + 8

        self.send_command(f"ATSH{ecu_id:03X}")

        # UDS Service 0x14: Clear DTC, 0xFFFFFF = all groups
        response = self.send_command("14 FF FF FF")

        if not response:
            return False

        lines = response.strip().split('\n')
        payload = self._parse_isotp_response(lines, response_id)

        # Positive response is 0x54
        return len(payload) > 0 and payload[0] == 0x54

    def _check_for_first_frame(self, lines: Sequence[str], response_id: int) -> Optional[tuple[int, List[int]]]:
        """Check if response contains a First Frame requiring flow control.

        Args:
            lines: Response lines from ELM327
            response_id: Expected CAN ID

        Returns:
            Tuple of (total_length, first_frame_data) if First Frame found, None otherwise
        """
        expected_header = f"{response_id:X}".upper()

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

            if frame_type == 1:  # First Frame
                total_length = ((pci & 0x0F) << 8) | data_bytes[1]
                return (total_length, data_bytes[2:])

        return None

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
            line = line.strip()
            if not line:
                continue

            # Parse line - handle both spaced and compact formats
            # Spaced: "7BB 10 29 61 01 00 00 05 C9"
            # Compact: "7BB102961010000005C9"
            data_bytes: List[int] = []
            if ' ' in line:
                parts = line.split()
                header = parts[0].upper()
                if header != expected_header and not header.endswith(expected_header):
                    continue
                try:
                    data_bytes = [int(part, 16) for part in parts[1:]]
                except ValueError:
                    continue
            else:
                # Compact format - header is first 3 chars, rest is hex pairs
                line_upper = line.upper()
                if not line_upper.startswith(expected_header):
                    continue
                hex_data = line_upper[len(expected_header):]
                if len(hex_data) < 2:
                    continue
                try:
                    data_bytes = [int(hex_data[i:i+2], 16) for i in range(0, len(hex_data), 2)]
                except ValueError:
                    continue

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
    # Strip response prefix (service response + PID)
    # Response service is request service + 0x40
    # PID can be 1 or 2 bytes depending on value
    if len(response_bytes) >= 2:
        response_service = pid.service + 0x40
        if response_bytes[0] == response_service:
            if pid.data_identifier <= 0xFF:
                # 1-byte PID: strip 2 bytes (service + pid)
                if len(response_bytes) >= 2 and response_bytes[1] == pid.data_identifier:
                    response_bytes = response_bytes[2:]
            else:
                # 2-byte PID: strip 3 bytes (service + 2-byte pid)
                pid_bytes = pid.data_identifier.to_bytes(2, "big")
                if len(response_bytes) >= 3 and response_bytes[1:3] == pid_bytes:
                    response_bytes = response_bytes[3:]

    result = {}
    for signal in pid.signals:
        start_byte = signal.start_bit // 8
        num_bytes = signal.length // 8

        # Handle special encodings
        if signal.encoding == "array_u16_be":
            # Parse as array of big-endian 16-bit values
            values = []
            end_byte = start_byte + num_bytes
            if end_byte <= len(response_bytes):
                for i in range(start_byte, end_byte, 2):
                    if i + 1 < len(response_bytes):
                        val = (response_bytes[i] << 8) | response_bytes[i + 1]
                        scaled = val * signal.scale + signal.offset
                        values.append(scaled)
            result[signal.key] = values
            continue

        # Standard scalar extraction
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


def decode_broadcast_frame(data: bytes, frame: BroadcastFrame) -> Dict[str, Any]:
    """Decode a broadcast CAN frame using signal definitions.

    Args:
        data: Raw CAN frame data bytes
        frame: Broadcast frame definition with signals

    Returns:
        Dictionary of signal key -> decoded value
    """
    result = {}

    for signal in frame.signals:
        start_byte = signal.start_bit // 8
        bit_in_byte = signal.start_bit % 8

        # Calculate how many bytes we need
        bits_needed = signal.length
        num_bytes = (bit_in_byte + bits_needed + 7) // 8

        if start_byte + num_bytes > len(data):
            continue

        # Extract the raw value
        value = 0
        for i in range(num_bytes):
            value = (value << 8) | data[start_byte + i]

        # Shift to align the bits we want
        # Total bits we have: num_bytes * 8
        # We want bits starting at bit_in_byte
        # Shift right by: (num_bytes * 8) - bit_in_byte - bits_needed
        shift = (num_bytes * 8) - bit_in_byte - bits_needed
        if shift > 0:
            value >>= shift

        # Mask to get only the bits we need
        mask = (1 << bits_needed) - 1
        value &= mask

        # Handle signed values
        if signal.signed and value >= (1 << (bits_needed - 1)):
            value -= (1 << bits_needed)

        # Apply formula if present (e.g., "value >> 1" or "(data[1] << 4) | (data[2] >> 4)")
        if signal.formula:
            try:
                value = eval(signal.formula, {"value": value, "data": data})
            except Exception:
                pass

        # Apply scaling and offset
        scaled = value * signal.scale + signal.offset
        result[signal.key] = scaled

    return result