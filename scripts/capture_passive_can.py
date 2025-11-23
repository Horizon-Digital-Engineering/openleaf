#!/usr/bin/env python3
"""Capture passive Car-CAN broadcasts from Nissan Leaf.

This script puts an ELM327 adapter into monitor mode (ATMA) to passively
listen to all CAN messages on the Car-CAN bus without sending any queries.

Usage:
    python scripts/capture_passive_can.py --port /dev/rfcomm0 --duration 60
    python scripts/capture_passive_can.py --ble AA:BB:CC:DD:EE:FF --duration 120

The script will create a timestamped log file in logs/passive_*.log
"""

import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import serial  # type: ignore
except ImportError:
    serial = None

try:
    from bleak import BleakClient, BleakScanner  # type: ignore
except ImportError:
    BleakClient = None
    BleakScanner = None


class SerialCANMonitor:
    """Monitor CAN bus via serial ELM327 adapter."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Optional[serial.Serial] = None

    def connect(self) -> None:
        """Open serial connection and initialize ELM327."""
        if serial is None:
            raise ImportError("pyserial is required. Install: pip install pyserial")

        print(f"Opening {self.port} @ {self.baudrate}...")
        self._serial = serial.Serial(self.port, baudrate=self.baudrate, timeout=self.timeout)
        time.sleep(0.5)

        # Initialize ELM327
        init_commands = ["ATZ", "ATI", "ATL1", "ATH1", "ATS1", "ATAL", "ATSP6"]
        for cmd in init_commands:
            self._write(cmd)
            response = self._read_until_prompt()
            print(f"  {cmd} -> {response[:50]}...")

    def start_monitoring(self) -> None:
        """Put ELM327 into monitor-all mode."""
        print("\nStarting passive CAN monitoring (ATMA)...")
        self._write("ATMA")
        # Don't wait for prompt - we're in streaming mode now
        time.sleep(0.2)

    def read_frames(self) -> list[str]:
        """Read available CAN frames from buffer."""
        if not self._serial:
            return []

        frames = []
        while self._serial.in_waiting > 0:
            line = self._serial.readline().decode('ascii', errors='ignore').strip()
            if line and line != '>' and not line.startswith('AT'):
                frames.append(line)
        return frames

    def stop_monitoring(self) -> None:
        """Stop monitor mode."""
        if self._serial:
            print("\nStopping monitor mode...")
            self._serial.write(b'\r')  # Send carriage return to exit ATMA
            time.sleep(0.5)
            self._serial.write(b'ATZ\r')  # Reset
            time.sleep(1)

    def close(self) -> None:
        """Close serial connection."""
        if self._serial:
            self._serial.close()

    def _write(self, command: str) -> None:
        """Write command to serial port."""
        if self._serial:
            self._serial.write((command + '\r').encode('ascii'))

    def _read_until_prompt(self) -> str:
        """Read until '>' prompt."""
        if not self._serial:
            return ""
        result = []
        while True:
            line = self._serial.readline().decode('ascii', errors='ignore').strip()
            if not line:
                break
            if line == '>':
                break
            result.append(line)
        return ' '.join(result)


class BleCANMonitor:
    """Monitor CAN bus via BLE ELM327 adapter."""

    def __init__(self, address: str,
                 service_uuid: str = "0000ffe0-0000-1000-8000-00805f9b34fb",
                 write_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb",
                 notify_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb"):
        if BleakClient is None:
            raise ImportError("bleak is required for BLE. Install: pip install bleak")

        self.address = address
        self.service_uuid = service_uuid
        self.write_uuid = write_uuid
        self.notify_uuid = notify_uuid
        self._client: Optional[BleakClient] = None
        self._rx_buffer = ""
        self._frame_queue: list[str] = []

    async def connect(self) -> None:
        """Connect to BLE adapter and initialize."""
        print(f"Connecting to BLE device {self.address}...")
        self._client = BleakClient(self.address)
        await self._client.connect()

        # Start notifications
        await self._client.start_notify(self.notify_uuid, self._on_notify)

        print("Initializing ELM327...")
        init_commands = ["ATZ", "ATI", "ATL1", "ATH1", "ATS1", "ATAL", "ATSP6"]
        for cmd in init_commands:
            await self._write(cmd)
            await asyncio.sleep(0.3)
            response = self._drain_queue()
            print(f"  {cmd} -> {response[:50]}...")

    async def start_monitoring(self) -> None:
        """Put ELM327 into monitor-all mode."""
        print("\nStarting passive CAN monitoring (ATMA)...")
        await self._write("ATMA")
        await asyncio.sleep(0.2)

    def read_frames(self) -> list[str]:
        """Read available CAN frames from queue."""
        frames = self._frame_queue.copy()
        self._frame_queue.clear()
        return frames

    async def stop_monitoring(self) -> None:
        """Stop monitor mode."""
        print("\nStopping monitor mode...")
        if self._client:
            await self._client.write_gatt_char(self.write_uuid, b'\r', response=True)
            await asyncio.sleep(0.5)
            await self._write("ATZ")
            await asyncio.sleep(1)

    async def close(self) -> None:
        """Disconnect from BLE device."""
        if self._client and self._client.is_connected:
            await self._client.stop_notify(self.notify_uuid)
            await self._client.disconnect()

    async def _write(self, command: str) -> None:
        """Write command to BLE characteristic."""
        if self._client:
            payload = (command + '\r').encode('ascii')
            await self._client.write_gatt_char(self.write_uuid, payload, response=True)

    def _on_notify(self, sender, data: bytearray) -> None:
        """Handle incoming BLE notifications."""
        text = data.decode('ascii', errors='ignore')
        self._rx_buffer += text

        # Process complete lines
        while '\r' in self._rx_buffer or '\n' in self._rx_buffer:
            self._rx_buffer = self._rx_buffer.replace('\r', '\n')
            if '\n' in self._rx_buffer:
                line, self._rx_buffer = self._rx_buffer.split('\n', 1)
                line = line.strip()
                if line and line != '>' and not line.startswith('AT'):
                    self._frame_queue.append(line)

    def _drain_queue(self) -> str:
        """Drain frame queue to string."""
        result = ' '.join(self._frame_queue)
        self._frame_queue.clear()
        return result


async def capture_ble(args) -> None:
    """Capture CAN frames via BLE adapter."""
    monitor = BleCANMonitor(args.ble)
    log_path = Path(args.output) / f"passive_ble_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        await monitor.connect()
        await monitor.start_monitoring()

        print(f"\nCapturing CAN frames for {args.duration} seconds...")
        print(f"Writing to: {log_path}")
        print("Press Ctrl+C to stop early\n")

        start_time = time.time()
        frame_count = 0

        with open(log_path, 'w', encoding='utf-8') as log_file:
            log_file.write(f"# Passive Car-CAN capture via BLE\n")
            log_file.write(f"# Device: {args.ble}\n")
            log_file.write(f"# Started: {datetime.now().isoformat()}\n")
            log_file.write(f"# Format: <timestamp> <can_id> <data_bytes>\n\n")

            while time.time() - start_time < args.duration:
                frames = monitor.read_frames()

                for frame in frames:
                    timestamp = time.time()
                    log_file.write(f"{timestamp:.6f} {frame}\n")
                    log_file.flush()
                    frame_count += 1

                    if frame_count % 100 == 0:
                        elapsed = time.time() - start_time
                        print(f"Captured {frame_count} frames in {elapsed:.1f}s ({frame_count/elapsed:.1f} fps)")

                await asyncio.sleep(0.01)  # Small delay to prevent busy loop

        await monitor.stop_monitoring()

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        await monitor.close()

    print(f"\nCaptured {frame_count} frames total")
    print(f"Log saved to: {log_path}")


def capture_serial(args) -> None:
    """Capture CAN frames via serial adapter."""
    monitor = SerialCANMonitor(args.port)
    log_path = Path(args.output) / f"passive_serial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        monitor.connect()
        monitor.start_monitoring()

        print(f"\nCapturing CAN frames for {args.duration} seconds...")
        print(f"Writing to: {log_path}")
        print("Press Ctrl+C to stop early\n")

        start_time = time.time()
        frame_count = 0

        with open(log_path, 'w', encoding='utf-8') as log_file:
            log_file.write(f"# Passive Car-CAN capture via Serial\n")
            log_file.write(f"# Port: {args.port}\n")
            log_file.write(f"# Started: {datetime.now().isoformat()}\n")
            log_file.write(f"# Format: <timestamp> <can_id> <data_bytes>\n\n")

            while time.time() - start_time < args.duration:
                frames = monitor.read_frames()

                for frame in frames:
                    timestamp = time.time()
                    log_file.write(f"{timestamp:.6f} {frame}\n")
                    log_file.flush()
                    frame_count += 1

                    if frame_count % 100 == 0:
                        elapsed = time.time() - start_time
                        print(f"Captured {frame_count} frames in {elapsed:.1f}s ({frame_count/elapsed:.1f} fps)")

                time.sleep(0.01)

        monitor.stop_monitoring()

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        monitor.close()

    print(f"\nCaptured {frame_count} frames total")
    print(f"Log saved to: {log_path}")


async def scan_for_ble_devices(timeout: float = 5.0) -> List[Tuple[str, str]]:
    """Scan for BLE devices and return list of (address, name) tuples."""
    if BleakScanner is None:
        raise ImportError("bleak is required for BLE scanning. Install: pip install bleak")

    print(f"Scanning for BLE devices for {timeout} seconds...")
    devices = await BleakScanner.discover(timeout=timeout)

    result = []
    for device in devices:
        name = device.name or "(unnamed)"
        result.append((device.address, name))

    return result


async def choose_ble_device() -> str:
    """Scan for BLE devices and let user choose one."""
    devices = await scan_for_ble_devices()

    if not devices:
        print("No BLE devices found!")
        sys.exit(1)

    # Find OBD devices (case-insensitive search for OBD, ELM, Vgate, etc.)
    obd_devices = []
    for addr, name in devices:
        name_lower = name.lower()
        if any(keyword in name_lower for keyword in ['obd', 'elm', 'vgate', 'obdii', 'obd2']):
            obd_devices.append((addr, name))

    # Display devices
    print("\nFound BLE devices:")
    for i, (addr, name) in enumerate(devices, 1):
        is_obd = (addr, name) in obd_devices
        marker = " [OBD DEVICE]" if is_obd else ""
        print(f"  {i}. {addr:17} - {name}{marker}")

    # Default selection
    default_choice = None
    if len(obd_devices) == 1:
        # Single OBD device found - use it as default
        default_choice = devices.index(obd_devices[0]) + 1
        print(f"\nDefault selection: {default_choice} (OBD device found)")
    elif len(obd_devices) > 1:
        # Multiple OBD devices - let user choose
        print("\nMultiple OBD devices found. Please choose one.")

    # Get user choice
    while True:
        try:
            if default_choice:
                prompt = f"Select device [1-{len(devices)}] (default: {default_choice}): "
                choice = await asyncio.to_thread(input, prompt)
                choice = choice.strip()
                if not choice:
                    choice = str(default_choice)
            else:
                prompt = f"Select device [1-{len(devices)}]: "
                choice = await asyncio.to_thread(input, prompt)
                choice = choice.strip()

            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                selected_addr, selected_name = devices[idx]
                print(f"\nSelected: {selected_addr} - {selected_name}")
                return selected_addr
            else:
                print(f"Please enter a number between 1 and {len(devices)}")
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nCancelled by user")
            sys.exit(0)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Capture passive Car-CAN broadcasts from Nissan Leaf",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan for BLE adapters and choose one
  python scripts/capture_passive_can.py --scan --duration 60

  # Capture via serial Bluetooth adapter for 60 seconds
  python scripts/capture_passive_can.py --port /dev/rfcomm0 --duration 60

  # Capture via BLE adapter for 2 minutes
  python scripts/capture_passive_can.py --ble AA:BB:CC:DD:EE:FF --duration 120

  # Capture to custom output directory
  python scripts/capture_passive_can.py --port /dev/rfcomm0 --output ./my_logs
"""
    )

    # Connection options
    conn_group = parser.add_mutually_exclusive_group(required=True)
    conn_group.add_argument('--scan', action='store_true',
                           help='Scan for BLE adapters and choose one')
    conn_group.add_argument('--port', help='Serial port (e.g., /dev/rfcomm0)')
    conn_group.add_argument('--ble', help='BLE adapter MAC address (e.g., AA:BB:CC:DD:EE:FF)')

    # Capture options
    parser.add_argument('--duration', type=int, default=60,
                       help='Capture duration in seconds (default: 60)')
    parser.add_argument('--output', default='./logs',
                       help='Output directory for log files (default: ./logs)')

    args = parser.parse_args()

    # Handle scanning option
    if args.scan:
        # Scan and choose a BLE device
        selected_address = asyncio.run(choose_ble_device())
        # Update args to use the selected BLE address
        args.ble = selected_address
        args.scan = False  # Clear scan flag

    # Now proceed with capture
    if args.ble:
        asyncio.run(capture_ble(args))
    else:
        capture_serial(args)


if __name__ == '__main__':
    main()
