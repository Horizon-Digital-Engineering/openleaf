"""Playback transport for replaying recorded sessions."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from .base import Transport

LOGGER = logging.getLogger(__name__)


class PlaybackTransport(Transport):
    """Replays recorded vehicle data from log files.

    Supports multiple formats:
    - OpenLeaf JSON format (native)
    - LeafSpy Pro CSV export
    - Raw CAN log files
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        format: str = "auto",
        loop_playback: bool = True,
        playback_speed: float = 1.0,
        update_interval_sec: float = 0.5,
    ):
        """Initialize playback transport.

        Args:
            file_path: Path to the log file to replay
            format: File format ('json', 'leafspy', 'can', 'auto' to detect)
            loop_playback: Whether to loop when reaching end of file
            playback_speed: Speed multiplier (2.0 = double speed)
            update_interval_sec: Update interval for state updates
        """
        self.file_path = Path(file_path)
        self.format = format
        self.loop_playback = loop_playback
        self.playback_speed = playback_speed
        self.update_interval_sec = update_interval_sec

        if not self.file_path.exists():
            raise FileNotFoundError(f"Playback file not found: {file_path}")

        # Auto-detect format
        if format == "auto":
            self.format = self._detect_format()
            LOGGER.info(f"Auto-detected format: {self.format}")

        # Load the data
        self.data = self._load_data()
        self.current_index = 0
        self.start_time = None
        self.playback_start_time = None

    def _detect_format(self) -> str:
        """Auto-detect file format based on extension and content."""
        ext = self.file_path.suffix.lower()

        if ext == ".json":
            return "json"
        elif ext == ".csv":
            # Check if it looks like LeafSpy format
            with open(self.file_path, 'r') as f:
                header = f.readline().lower()
                if 'gids' in header or 'soc' in header:
                    return "leafspy"
            return "csv"
        elif ext in [".log", ".txt"]:
            return "can"

        # Try to detect by content
        with open(self.file_path, 'r') as f:
            first_line = f.readline().strip()
            if first_line.startswith('{'):
                return "json"
            elif ',' in first_line:
                return "leafspy"
            else:
                return "can"

    def _load_data(self) -> List[Dict[str, Any]]:
        """Load and parse the data file."""
        if self.format == "json":
            return self._load_json()
        elif self.format == "leafspy":
            return self._load_leafspy()
        elif self.format == "can":
            return self._load_can()
        else:
            raise ValueError(f"Unknown format: {self.format}")

    def _load_json(self) -> List[Dict[str, Any]]:
        """Load OpenLeaf JSON format."""
        with open(self.file_path, 'r') as f:
            data = json.load(f)

        # Handle both single snapshot and array of snapshots
        if isinstance(data, dict):
            return [data]
        return data

    def _load_leafspy(self) -> List[Dict[str, Any]]:
        """Load LeafSpy Pro CSV export."""
        import csv

        data = []
        with open(self.file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map LeafSpy fields to OpenLeaf state
                state = {}

                # Battery data
                if 'Gids' in row:
                    state['gids'] = int(row['Gids'])
                if 'SOC' in row:
                    state['soc_percent'] = float(row['SOC'].rstrip('%'))
                if 'Hx' in row:
                    state['soh_percent'] = float(row['Hx'].rstrip('%'))
                if 'Pack Volts' in row:
                    state['pack_voltage'] = float(row['Pack Volts'])
                if 'Pack Amps' in row:
                    state['pack_current'] = float(row['Pack Amps'])

                # Temperature
                if 'Batt Temp' in row:
                    temps = row['Batt Temp'].split('/')
                    if len(temps) >= 3:
                        state['temp1_celsius'] = float(temps[0])
                        state['temp2_celsius'] = float(temps[1])
                        state['temp3_celsius'] = float(temps[2])

                # Vehicle data
                if 'Speed' in row:
                    state['speed_kmh'] = float(row['Speed'])
                if 'Odometer' in row:
                    state['odometer_km'] = float(row['Odometer'])

                # Cell voltages (if present)
                cell_volts = []
                for i in range(1, 97):  # Up to 96 cells
                    cell_key = f'Cell{i:02d}'
                    if cell_key in row and row[cell_key]:
                        cell_volts.append(float(row[cell_key]))
                if cell_volts:
                    state['cell_voltages'] = cell_volts

                # Timestamp
                if 'Time' in row:
                    state['_timestamp'] = row['Time']

                data.append(state)

        LOGGER.info(f"Loaded {len(data)} records from LeafSpy CSV")
        return data

    def _load_can(self) -> List[Dict[str, Any]]:
        """Load raw CAN log file."""
        # This would parse raw CAN messages and decode them
        # For now, return empty list - this needs the CAN decoder logic
        LOGGER.warning("CAN log playback not yet implemented")
        return []

    def loop(self) -> Iterator[Dict[str, Any]]:
        """Generate state updates from recorded data."""
        if not self.data:
            LOGGER.warning("No data to replay")
            return

        self.start_time = time.time()
        self.playback_start_time = time.time()

        while True:
            # Get current data point
            if self.current_index >= len(self.data):
                if self.loop_playback:
                    self.current_index = 0
                    self.playback_start_time = time.time()
                    LOGGER.info("Looping playback")
                else:
                    LOGGER.info("Playback complete")
                    break

            # Emit current state
            state = self.data[self.current_index].copy()

            # Add playback metadata
            state['_playback'] = {
                'file': str(self.file_path),
                'format': self.format,
                'index': self.current_index,
                'total': len(self.data),
                'speed': self.playback_speed,
            }

            yield state

            # Move to next data point
            self.current_index += 1

            # Sleep based on playback speed
            sleep_time = self.update_interval_sec / self.playback_speed
            time.sleep(sleep_time)

    def send_command(self, command: str) -> None:
        """Playback doesn't support commands."""
        LOGGER.warning(f"Playback transport ignoring command: {command}")


class PlaybackRecorder:
    """Records vehicle state for later playback."""

    def __init__(
        self,
        output_path: Union[str, Path],
        format: str = "json",
    ):
        """Initialize recorder.

        Args:
            output_path: Path to save the recording
            format: Output format ('json', 'csv')
        """
        self.output_path = Path(output_path)
        self.format = format
        self.data: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def record_state(self, state: Dict[str, Any]) -> None:
        """Record a state snapshot."""
        # Add timestamp
        snapshot = state.copy()
        snapshot['_timestamp'] = time.time() - self.start_time

        self.data.append(snapshot)

    def save(self) -> None:
        """Save the recording to file."""
        LOGGER.info(f"Saving {len(self.data)} snapshots to {self.output_path}")

        if self.format == "json":
            with open(self.output_path, 'w') as f:
                json.dump(self.data, f, indent=2)
        else:
            raise NotImplementedError(f"Format {self.format} not yet supported")

        LOGGER.info(f"Recording saved to {self.output_path}")