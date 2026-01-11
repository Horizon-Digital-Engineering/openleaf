"""Unified OBD2 transport with pluggable connections."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

import yaml

from .base import Transport
from .connections import BLEConnection, OBDConnection, SerialConnection
from .elm327 import (
    BroadcastFrame,
    ELM327Protocol,
    PidDefinition,
    PidSignal,
    decode_broadcast_frame,
    decode_pid_response,
)

LOGGER = logging.getLogger(__name__)


class OBD2Transport(Transport):
    """OBD2 transport that supports BLE, Serial, and Bluetooth Classic connections."""

    def __init__(
        self,
        connection_type: str = "ble",
        # Connection settings
        ble_address: Optional[str] = None,
        ble_service_uuid: str = "0000ffe0-0000-1000-8000-00805f9b34fb",
        ble_write_char_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb",
        ble_notify_char_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb",
        serial_port: Optional[str] = None,
        serial_baudrate: int = 115200,
        # Common settings
        timeout_sec: float = 1.0,
        update_interval_sec: float = 0.5,
        pid_path: Union[str, Path] = "pids/leaf.yaml",
        reconnect_delay_sec: float = 5.0,
        enable_flow_control: bool = False,
        # Recording settings
        record_enabled: bool = False,
        record_path: Optional[Union[str, Path]] = None,
        # Logging
        connection_logger: Optional[logging.Logger] = None,
    ):
        """Initialize OBD2 transport.

        Args:
            connection_type: Type of connection ('ble', 'serial', 'bluetooth')
            ble_address: BLE MAC address or UUID (for BLE connection)
            ble_service_uuid: GATT service UUID (for BLE)
            ble_write_char_uuid: Write characteristic UUID (for BLE)
            ble_notify_char_uuid: Notify characteristic UUID (for BLE)
            serial_port: Serial port path (for serial/bluetooth connection)
            serial_baudrate: Serial baudrate (for serial/bluetooth)
            timeout_sec: Communication timeout
            update_interval_sec: Update interval for polling PIDs
            pid_path: Path to PID definition YAML file
            reconnect_delay_sec: Delay before reconnection attempts
            enable_flow_control: Enable ISO-TP flow control (usually not needed)
            record_enabled: Enable recording to file
            record_path: Path for recording file
            connection_logger: Optional logger for connection events
        """
        self.connection_type = connection_type.lower()
        self.timeout_sec = timeout_sec
        self.update_interval_sec = update_interval_sec
        self.reconnect_delay_sec = reconnect_delay_sec
        self.enable_flow_control = enable_flow_control
        self.logger = connection_logger or LOGGER

        # Create the appropriate connection
        self.connection: OBDConnection
        if self.connection_type == "ble":
            if not ble_address:
                raise ValueError("BLE address required for BLE connection")
            self.connection = BLEConnection(
                address=ble_address,
                service_uuid=ble_service_uuid,
                write_char_uuid=ble_write_char_uuid,
                notify_char_uuid=ble_notify_char_uuid,
                timeout=timeout_sec,
            )
        elif self.connection_type in ["serial", "bluetooth", "usb"]:
            if not serial_port:
                raise ValueError("Serial port required for serial/bluetooth connection")
            self.connection = SerialConnection(
                port=serial_port,
                baudrate=serial_baudrate,
                timeout=timeout_sec,
            )
        else:
            raise ValueError(f"Unknown connection type: {connection_type}")

        # Create protocol handler
        self.protocol = ELM327Protocol(self.connection, self.logger)

        # Load PID and broadcast definitions
        self.pid_path = Path(pid_path)
        self.pids, self.broadcast_frames = self._load_definitions()

        # Recording setup
        self.record_enabled = record_enabled
        self.record_data: List[Dict[str, Any]] = []
        if record_enabled and record_path:
            self.record_path = Path(record_path)
            # Replace {timestamp} placeholder
            if "{timestamp}" in str(self.record_path):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                self.record_path = Path(str(self.record_path).replace("{timestamp}", timestamp))
        else:
            self.record_path = None

        # State tracking
        self._last_poll_times: Dict[str, float] = {}
        self._debug_log: List[str] = []
        self._start_time = time.time()

    def _load_definitions(self) -> tuple[List[PidDefinition], Dict[int, BroadcastFrame]]:
        """Load PID and broadcast frame definitions from YAML file.

        Returns:
            Tuple of (list of PidDefinitions, dict of CAN ID -> BroadcastFrame)
        """
        if not self.pid_path.exists():
            self.logger.warning(f"PID file not found: {self.pid_path}")
            return [], {}

        with open(self.pid_path, "r") as f:
            data = yaml.safe_load(f)

        # Helper to parse hex IDs
        def parse_id(value):
            if isinstance(value, int):
                return value
            s = str(value)
            if s.startswith("0x") or s.startswith("0X"):
                return int(s, 16)
            return int(s, 16) if all(c in "0123456789abcdefABCDEF" for c in s) else int(s)

        # Helper to parse signal definitions
        def parse_signal(signal_data: dict) -> Optional[PidSignal]:
            if "start_bit" in signal_data:
                start_bit = signal_data["start_bit"]
                length = signal_data["length"]
            elif "byte_offset" in signal_data:
                start_bit = signal_data["byte_offset"] * 8
                length = signal_data.get("byte_length", 1) * 8
            else:
                return None

            return PidSignal(
                key=signal_data["key"],
                start_bit=start_bit,
                length=length,
                scale=signal_data.get("scale", 1.0),
                offset=signal_data.get("offset", 0.0),
                enum=signal_data.get("enum"),
                encoding=signal_data.get("encoding"),
                signed=signal_data.get("signed", False),
                formula=signal_data.get("formula"),
            )

        # Load broadcast frames
        broadcast_frames: Dict[int, BroadcastFrame] = {}
        for frame_data in data.get("broadcast_frames", []):
            can_id = parse_id(frame_data["id"])
            signals = []
            for signal_data in frame_data.get("signals", []):
                signal = parse_signal(signal_data)
                if signal:
                    signals.append(signal)

            if signals:
                broadcast_frames[can_id] = BroadcastFrame(
                    can_id=can_id,
                    name=frame_data["name"],
                    signals=signals,
                )

        # Load query PIDs
        pid_list = data.get("query_pids", data.get("pids", []))
        pids = []
        for pid_data in pid_list:
            signals = []
            for signal_data in pid_data.get("signals", []):
                signal = parse_signal(signal_data)
                if signal:
                    signals.append(signal)
                else:
                    self.logger.warning(f"Signal {signal_data.get('key')} missing offset info, skipping")

            pid = PidDefinition(
                name=pid_data["name"],
                request_id=parse_id(pid_data["request_id"]),
                response_id=parse_id(pid_data["response_id"]),
                service=parse_id(pid_data["service"]),
                data_identifier=parse_id(pid_data["data_identifier"]),
                signals=signals,
                poll_interval_sec=pid_data.get("poll_interval_sec"),
            )
            pids.append(pid)

        self.logger.info(f"Loaded {len(pids)} PIDs and {len(broadcast_frames)} broadcast frames from {self.pid_path}")
        return pids, broadcast_frames

    def loop(self) -> Iterator[Dict[str, Any]]:
        """Generate state updates from the vehicle."""
        self._log_transport_start()

        while True:
            try:
                # Ensure connection is established
                if not self.connection.is_connected():
                    self.logger.info("Connecting to OBD2 adapter...")
                    self.connection.connect_sync()
                    self.protocol.initialized = False  # Force re-initialization

                # Initialize protocol if needed
                if not self.protocol.initialized:
                    self.protocol.initialize()

                # Poll PIDs and collect state
                state = self._poll_all_pids()

                # Add metadata
                state["_transport"] = {
                    "type": "obd2",
                    "connection": self.connection_type,
                    "connected": True,
                    "runtime": time.time() - self._start_time,
                }

                # Record if enabled
                if self.record_enabled and self.record_data is not None:
                    self.record_data.append({
                        "timestamp": time.time() - self._start_time,
                        "state": state.copy(),
                    })

                yield state

                # Sleep before next update
                time.sleep(self.update_interval_sec)

            except (ConnectionError, OSError) as e:
                self.logger.error(f"Connection error: {e}")
                self._record_event("error", f"Connection lost: {e}")

                # Disconnect and wait before retry
                try:
                    self.connection.disconnect_sync()
                except Exception:
                    pass

                yield {
                    "_transport": {
                        "type": "obd2",
                        "connection": self.connection_type,
                        "connected": False,
                        "error": str(e),
                    }
                }

                time.sleep(self.reconnect_delay_sec)

            except KeyboardInterrupt:
                self.logger.info("Shutting down OBD2 transport")
                break

            except Exception as e:
                self.logger.error(f"Unexpected error: {e}", exc_info=True)
                self._record_event("error", f"Unexpected: {e}")
                time.sleep(self.update_interval_sec)

        # Save recording on exit
        if self.record_enabled and self.record_path and self.record_data:
            self._save_recording()

        # Clean disconnect
        try:
            self.connection.disconnect_sync()
        except Exception:
            pass

    def _poll_all_pids(self) -> Dict[str, Any]:
        """Poll all PIDs and return combined state."""
        state = {}
        current_time = time.time()

        for pid in self.pids:
            # Check if it's time to poll this PID
            if pid.poll_interval_sec:
                last_poll = self._last_poll_times.get(pid.name, 0)
                if current_time - last_poll < pid.poll_interval_sec:
                    continue

            try:
                # Query the PID
                response = self.protocol.query_pid(pid)

                # Decode the response
                if response:
                    values = decode_pid_response(response, pid)
                    state.update(values)
                    self._last_poll_times[pid.name] = current_time
                    self._record_event("pid", f"{pid.name}: {values}")

            except Exception as e:
                self.logger.debug(f"Failed to query {pid.name}: {e}")
                self._record_event("error", f"PID {pid.name}: {e}")

        # Poll broadcast messages for SOH/SOC (every 5 seconds)
        if current_time - self._last_poll_times.get("broadcast", 0) >= 5.0:
            try:
                broadcast_values = self.poll_broadcast_messages(duration_sec=1.5)
                state.update(broadcast_values)
                self._last_poll_times["broadcast"] = current_time
                if broadcast_values:
                    self._record_event("broadcast", f"Got: {broadcast_values}")
            except Exception as e:
                self.logger.debug(f"Broadcast monitoring failed: {e}")

        # Calculate derived values
        self._calculate_derived_values(state)

        return state

    def _calculate_derived_values(self, state: Dict[str, Any]) -> None:
        """Calculate derived values from raw sensor data."""
        # Cell voltage delta (max - min)
        if "cell_v_max" in state and "cell_v_min" in state:
            delta = state["cell_v_max"] - state["cell_v_min"]
            state["cell_v_delta"] = delta
            state["cell_delta_mv"] = delta * 1000  # Also in mV

        # Average pack temperature (excluding sensor errors = 255)
        temps = []
        for key in ["temp_sensor_1", "temp_sensor_2", "temp_sensor_3", "temp_sensor_4"]:
            if key in state and state[key] != 255:
                temps.append(state[key])
        if temps:
            state["pack_temp_c"] = sum(temps) / len(temps)

    def poll_broadcast_messages(self, duration_sec: float = 1.0) -> Dict[str, Any]:
        """Poll for broadcast CAN messages (SOH, SOC, etc).

        Uses YAML-defined broadcast_frames for decoding - no hardcoded byte offsets.
        Note: These messages typically only appear when car ignition is ON.

        Args:
            duration_sec: How long to monitor

        Returns:
            Dictionary of decoded broadcast values
        """
        if not self.broadcast_frames:
            return {}

        # Get list of CAN IDs we have definitions for
        broadcast_ids = list(self.broadcast_frames.keys())

        try:
            frames = self.protocol.monitor_broadcast(broadcast_ids, duration_sec)
        except Exception as e:
            self.logger.debug(f"Broadcast monitoring failed: {e}")
            return {}

        result = {}

        # Decode each received frame using YAML definitions
        for can_id, data in frames.items():
            if can_id in self.broadcast_frames:
                frame_def = self.broadcast_frames[can_id]
                decoded = decode_broadcast_frame(data, frame_def)
                result.update(decoded)

        # Add gids alias for stored_energy_gids (backwards compatibility)
        if "stored_energy_gids" in result and "gids" not in result:
            result["gids"] = result["stored_energy_gids"]

        return result

    def _record_event(self, event_type: str, message: str) -> None:
        """Record an event to the debug log."""
        timestamp = time.time() - self._start_time
        self._debug_log.append(f"[{timestamp:.2f}] {event_type}: {message}")

        # Keep log size reasonable
        if len(self._debug_log) > 100:
            self._debug_log.pop(0)

    def _log_transport_start(self) -> None:
        """Log transport startup information."""
        self.logger.info("Starting OBD2 transport")
        self.logger.info(f"  Connection: {self.connection_type}")
        self.logger.info(f"  PIDs: {len(self.pids)} definitions loaded")
        self.logger.info(f"  Update interval: {self.update_interval_sec}s")
        if self.record_enabled:
            self.logger.info(f"  Recording to: {self.record_path}")

    def _save_recording(self) -> None:
        """Save recorded data to file."""
        if not self.record_path or not self.record_data:
            return

        self.logger.info(f"Saving {len(self.record_data)} recordings to {self.record_path}")

        # Ensure directory exists
        self.record_path.parent.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        with open(self.record_path, "w") as f:
            json.dump(self.record_data, f, indent=2)

        self.logger.info(f"Recording saved to {self.record_path}")

    def send_command(self, command: str) -> None:
        """Send a raw command to the OBD2 adapter.

        Args:
            command: Command to send (e.g., "CLEAR_DTC" to clear diagnostic codes)
        """
        if command == "CLEAR_DTC":
            # Send the clear DTC command (service 0x14)
            response = self.protocol.send_command("14")
            self.logger.info(f"Clear DTC response: {response}")
        else:
            # Send raw command
            response = self.protocol.send_command(command)
            self.logger.info(f"Command '{command}' response: {response}")

    def debug_log(self) -> List[str]:
        """Return recent debug log entries."""
        return self._debug_log.copy()