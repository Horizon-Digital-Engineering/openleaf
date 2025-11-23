#!/usr/bin/env python3
"""Parse captured passive Car-CAN logs from Nissan Leaf.

This script decodes known passive CAN broadcast messages from log files
created by capture_passive_can.py.

Usage:
    python scripts/parse_passive_can.py logs/passive_*.log
    python scripts/parse_passive_can.py logs/passive_*.log --summary
    python scripts/parse_passive_can.py logs/passive_*.log --can-id 5B3
"""

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CANFrame:
    """Represents a single CAN frame."""
    timestamp: float
    can_id: int
    data: bytes
    raw_line: str


@dataclass
class SignalDefinition:
    """Defines how to decode a signal from CAN data."""
    name: str
    byte_offset: int
    length: int  # in bytes
    scale: float = 1.0
    offset: float = 0.0
    signed: bool = False
    unit: str = ""
    description: str = ""


# Known passive broadcast messages on Car-CAN
# Source: docs/ref/leaf_can_obd_summary.md and community research

PASSIVE_MESSAGES = {
    0x5B3: {
        "name": "Battery Status Broadcast",
        "description": "SOH, GIDs, capacity",
        "signals": [
            SignalDefinition("soh_pct", 2, 1, scale=0.5, unit="%",
                           description="State of Health percentage"),
            SignalDefinition("gids", 4, 1, scale=1.0, unit="GIDs",
                           description="Battery capacity in GIDs (1 GID ≈ 80Wh)"),
        ]
    },
    0x5BC: {
        "name": "SOC Broadcast",
        "description": "State of Charge percentage",
        "signals": [
            SignalDefinition("soc_pct", 0, 2, scale=0.1, unit="%",
                           description="State of Charge (reported to dashboard)"),
        ]
    },
    0x1DB: {
        "name": "Charging Status",
        "description": "Charging state and HV voltage",
        "signals": [
            SignalDefinition("hv_voltage", 2, 2, scale=0.5, unit="V",
                           description="High voltage battery pack voltage"),
            SignalDefinition("charging", 0, 1, unit="bool",
                           description="Charging status flag"),
        ]
    },
    0x5C5: {
        "name": "Odometer Broadcast",
        "description": "Total vehicle distance",
        "signals": [
            SignalDefinition("odometer", 1, 3, scale=1.0, unit="km",
                           description="Total distance traveled"),
        ]
    },
    0x1DA: {
        "name": "Quick Charge Status",
        "description": "CHAdeMO quick charging state",
        "signals": []  # TBD - need to research byte layout
    },
    0x55B: {
        "name": "Speed and Power",
        "description": "Vehicle speed and motor power",
        "signals": [
            SignalDefinition("speed", 0, 2, scale=0.01, unit="km/h",
                           description="Vehicle speed"),
        ]
    },
}


def parse_can_line(line: str, line_num: int) -> Optional[CANFrame]:
    """Parse a single line from the capture log.

    Expected format: <timestamp> <can_id> <byte0> <byte1> ... <byte7>
    Example: 1234567890.123456 5B3 12 34 56 78 9A BC DE F0
    """
    line = line.strip()

    # Skip comments and empty lines
    if not line or line.startswith('#'):
        return None

    parts = line.split()
    if len(parts) < 2:
        return None

    try:
        timestamp = float(parts[0])
        can_id_str = parts[1].upper()

        # Parse CAN ID (might have spaces between bytes)
        can_id = int(can_id_str, 16)

        # Parse data bytes
        data_bytes = []
        for byte_str in parts[2:]:
            byte_str = byte_str.strip()
            if byte_str:
                data_bytes.append(int(byte_str, 16))

        data = bytes(data_bytes)

        return CANFrame(timestamp=timestamp, can_id=can_id, data=data, raw_line=line)

    except (ValueError, IndexError) as e:
        print(f"Warning: Could not parse line {line_num}: {line[:50]} - {e}")
        return None


def decode_signal(data: bytes, signal: SignalDefinition) -> Optional[float]:
    """Decode a signal from CAN data bytes."""
    try:
        # Extract bytes
        if signal.byte_offset + signal.length > len(data):
            return None

        value_bytes = data[signal.byte_offset:signal.byte_offset + signal.length]

        # Convert to integer (big-endian)
        raw_value = int.from_bytes(value_bytes, byteorder='big', signed=signal.signed)

        # Apply scale and offset
        decoded_value = (raw_value * signal.scale) + signal.offset

        return decoded_value

    except Exception:
        return None


def decode_frame(frame: CANFrame) -> Dict[str, Any]:
    """Decode all signals in a CAN frame."""
    message_def = PASSIVE_MESSAGES.get(frame.can_id)
    if not message_def:
        return {}

    decoded = {
        "message_name": message_def["name"],
        "description": message_def["description"],
        "signals": {}
    }

    for signal in message_def["signals"]:
        value = decode_signal(frame.data, signal)
        if value is not None:
            decoded["signals"][signal.name] = {
                "value": value,
                "unit": signal.unit,
                "description": signal.description
            }

    return decoded


def analyze_log(log_path: Path, filter_can_id: Optional[int] = None) -> None:
    """Analyze and display decoded CAN messages."""
    print(f"\nAnalyzing: {log_path}")
    print("=" * 80)

    frames: List[CANFrame] = []
    can_id_counts: Dict[int, int] = defaultdict(int)

    # Parse all frames
    with open(log_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            frame = parse_can_line(line, line_num)
            if frame:
                frames.append(frame)
                can_id_counts[frame.can_id] += 1

    print(f"\nTotal frames parsed: {len(frames)}")

    if not frames:
        print("No valid frames found in log file")
        return

    duration = frames[-1].timestamp - frames[0].timestamp
    print(f"Capture duration: {duration:.2f} seconds")
    print(f"Average rate: {len(frames)/duration:.1f} frames/second")

    # Show CAN ID frequency
    print(f"\nCAN IDs observed (total: {len(can_id_counts)} unique IDs):")
    print("-" * 80)

    sorted_ids = sorted(can_id_counts.items(), key=lambda x: x[1], reverse=True)
    for can_id, count in sorted_ids[:20]:  # Show top 20
        known = "✓" if can_id in PASSIVE_MESSAGES else " "
        message_name = PASSIVE_MESSAGES.get(can_id, {}).get("name", "Unknown")
        rate = count / duration
        print(f"  {known} 0x{can_id:03X}  {count:6d} frames  ({rate:6.1f}/s)  {message_name}")

    if len(sorted_ids) > 20:
        print(f"  ... and {len(sorted_ids) - 20} more CAN IDs")

    # Decode known messages
    print(f"\nDecoded Messages:")
    print("=" * 80)

    decoded_by_id: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

    for frame in frames:
        if filter_can_id and frame.can_id != filter_can_id:
            continue

        if frame.can_id in PASSIVE_MESSAGES:
            decoded = decode_frame(frame)
            if decoded and decoded.get("signals"):
                decoded["timestamp"] = frame.timestamp
                decoded["raw_data"] = frame.data.hex().upper()
                decoded_by_id[frame.can_id].append(decoded)

    # Display decoded messages
    for can_id in sorted(decoded_by_id.keys()):
        messages = decoded_by_id[can_id]
        if not messages:
            continue

        print(f"\n0x{can_id:03X} - {messages[0]['message_name']} ({len(messages)} frames)")
        print(f"  {messages[0]['description']}")
        print("-" * 80)

        # Show first, last, and some samples
        sample_indices = [0]
        if len(messages) > 1:
            sample_indices.append(len(messages) // 2)
            sample_indices.append(len(messages) - 1)

        for idx in sample_indices:
            msg = messages[idx]
            rel_time = msg["timestamp"] - frames[0].timestamp
            print(f"\n  [{rel_time:8.2f}s] Raw: {msg['raw_data']}")

            for sig_name, sig_data in msg["signals"].items():
                value = sig_data["value"]
                unit = sig_data["unit"]
                desc = sig_data["description"]
                print(f"    {sig_name:20s} = {value:10.2f} {unit:6s}  # {desc}")


def generate_summary(log_path: Path) -> None:
    """Generate a summary report of the capture."""
    print(f"\nSummary Report: {log_path}")
    print("=" * 80)

    frames: List[CANFrame] = []

    with open(log_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            frame = parse_can_line(line, line_num)
            if frame:
                frames.append(frame)

    if not frames:
        print("No frames to analyze")
        return

    # Calculate statistics per known message
    for can_id, msg_def in sorted(PASSIVE_MESSAGES.items()):
        matching_frames = [f for f in frames if f.can_id == can_id]

        if not matching_frames:
            print(f"\n0x{can_id:03X} - {msg_def['name']}: NOT SEEN")
            continue

        print(f"\n0x{can_id:03X} - {msg_def['name']}: {len(matching_frames)} frames")

        # Calculate min/max/avg for each signal
        for signal in msg_def["signals"]:
            values = []
            for frame in matching_frames:
                value = decode_signal(frame.data, signal)
                if value is not None:
                    values.append(value)

            if values:
                print(f"  {signal.name:20s}: min={min(values):8.2f}  max={max(values):8.2f}  "
                      f"avg={sum(values)/len(values):8.2f}  {signal.unit}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Parse and decode passive Car-CAN capture logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a capture log
  python scripts/parse_passive_can.py logs/passive_20250123_120000.log

  # Show summary statistics
  python scripts/parse_passive_can.py logs/passive_*.log --summary

  # Filter to specific CAN ID
  python scripts/parse_passive_can.py logs/passive_*.log --can-id 5B3
"""
    )

    parser.add_argument('log_file', type=Path, help='Path to capture log file')
    parser.add_argument('--summary', action='store_true',
                       help='Show summary statistics instead of detailed decode')
    parser.add_argument('--can-id', type=str,
                       help='Filter to specific CAN ID (hex, e.g., 5B3)')

    args = parser.parse_args()

    if not args.log_file.exists():
        print(f"Error: Log file not found: {args.log_file}")
        return

    filter_id = None
    if args.can_id:
        try:
            filter_id = int(args.can_id, 16)
        except ValueError:
            print(f"Error: Invalid CAN ID format: {args.can_id}")
            return

    if args.summary:
        generate_summary(args.log_file)
    else:
        analyze_log(args.log_file, filter_id)


if __name__ == '__main__':
    main()
