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

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0,
                 use_filters: bool = False, can_filter: Optional[str] = None):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.use_filters = use_filters
        self.can_filter = can_filter
        self._serial: Optional[serial.Serial] = None

    def connect(self) -> None:
        """Open serial connection and initialize ELM327."""
        if serial is None:
            raise ImportError("pyserial is required. Install: pip install pyserial")

        print(f"Opening {self.port} @ {self.baudrate}...")
        self._serial = serial.Serial(self.port, baudrate=self.baudrate, timeout=1.0)

        # Verify we can communicate with the adapter
        print("Testing connection...")
        self._serial.write(b'ATI\r')
        time.sleep(0.5)

        test_response = b''
        if self._serial.in_waiting > 0:
            test_response = self._serial.read(self._serial.in_waiting)
            print(f"Test response: {test_response}")
        else:
            raise RuntimeError(f"No response from adapter at {self.port}. Check connection and ensure device is powered on.")

        # Verify we got something back
        if len(test_response) == 0:
            raise RuntimeError(f"Adapter at {self.port} is not responding. Check that it's properly connected.")

        print(f"Connection verified! Adapter responded: {test_response.decode('ascii', errors='ignore').strip()}")
        time.sleep(0.2)

        # Initialize ELM327 for passive monitoring (same as BLE)
        init_commands = [
            ("ATZ", 2.0),     # Reset - needs longer delay
            ("ATI", 0.5),     # Identify
            ("ATL1", 0.5),    # Linefeeds ON (easier to parse)
            ("ATH1", 0.5),    # Headers ON (needed to see CAN IDs)
            ("ATS1", 0.5),    # Spaces ON (easier to parse)
            ("ATAL", 0.5),    # Allow long messages (ISO-TP multi-frame)
            ("ATSP6", 0.5),   # Set protocol to ISO 15765-4 CAN (11 bit ID, 500 kbaud)
        ]

        # Add filter configuration if requested
        if self.use_filters and self.can_filter:
            # Only use filter if explicitly requested by user
            init_commands.append((f"ATCRA {self.can_filter}", 0.5))
            print(f"Using CAN filter: {self.can_filter}")
        else:
            # Default: NO filters - capture everything (that's the point!)
            print("No filters - capturing ALL CAN traffic")

        for cmd, delay in init_commands:
            self._write(cmd)
            time.sleep(delay)  # Wait for command to complete
            response = self._read_until_prompt()
            print(f"  {cmd} -> {response}")
            # Check for errors
            if "?" in response or "ERROR" in response:
                print(f"    WARNING: Command may have failed!")

    def start_monitoring(self, use_atma: bool = True) -> None:
        """Put ELM327 into monitor mode.

        Args:
            use_atma: If True, use ATMA (monitor all). If False, use ATMR (filtered).
        """
        if use_atma:
            print("\nStarting passive CAN monitoring (ATMA)...")
            self._write("ATMA")
        else:
            print("\nStarting filtered CAN monitoring (ATMR)...")
            self._write("ATMR")

        # Give adapter time to enter monitor mode before we start reading
        time.sleep(0.5)

        # Check if command was rejected
        if self._serial and self._serial.in_waiting > 0:
            response = self._serial.read(self._serial.in_waiting).decode('ascii', errors='ignore')
            print(f"ATMA response: {response}")
            if "?" in response or "ERROR" in response:
                print("ERROR: ATMA command not supported or failed!")
        else:
            print("No immediate response from ATMA (this is normal - it starts streaming)")

    def read_frames(self) -> list[str]:
        """Read available CAN frames from buffer."""
        if not self._serial:
            return []

        frames = []
        while self._serial.in_waiting > 0:
            line = self._serial.readline().decode('ascii', errors='ignore').strip()
            # Filter out prompts, empty lines, and command echoes
            if line and line != '>' and not line.startswith('AT') and not line.startswith('ELM'):
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
        """Read until '>' prompt or timeout."""
        if not self._serial:
            return ""

        result = []
        start_time = time.time()
        timeout = 3.0  # 3 second timeout for response

        while (time.time() - start_time) < timeout:
            if self._serial.in_waiting > 0:
                # Read one byte at a time to catch the prompt
                char = self._serial.read(1).decode('ascii', errors='ignore')
                if char == '>':
                    break
                elif char == '\r':
                    continue  # Skip carriage returns
                elif char == '\n':
                    continue  # Skip linefeeds
                elif char.isprintable() or char == ' ':
                    result.append(char)
            else:
                # No data waiting, sleep briefly
                time.sleep(0.01)

        return ''.join(result).strip()


class BleCANMonitor:
    """Monitor CAN bus via BLE ELM327 adapter."""

    def __init__(self, address: str,
                 service_uuid: str = "0000ffe0-0000-1000-8000-00805f9b34fb",
                 write_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb",
                 notify_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb",
                 use_filters: bool = False,
                 can_filter: Optional[str] = None):
        if BleakClient is None:
            raise ImportError("bleak is required for BLE. Install: pip install bleak")

        self.address = address
        self.service_uuid = service_uuid
        self.write_uuid = write_uuid
        self.notify_uuid = notify_uuid
        self.use_filters = use_filters
        self.can_filter = can_filter
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

        print("Initializing ELM327 with optimized settings...")
        # Optimized settings: ATL0 and ATS0 reduce buffer usage
        init_commands = [
            "ATZ",     # Reset
            "ATI",     # Identify
            "ATL0",    # Linefeeds OFF (reduces buffer usage)
            "ATH1",    # Headers ON (needed to see CAN IDs)
            "ATS0",    # Spaces OFF (reduces buffer usage)
            "ATAL",    # Allow long messages (ISO-TP multi-frame)
            "ATSP6",   # Set protocol to ISO 15765-4 CAN (11 bit ID, 500 kbaud)
        ]

        # Add filter configuration if requested
        if self.use_filters and self.can_filter:
            # Only use filter if explicitly requested by user
            init_commands.append(f"ATCRA {self.can_filter}")
            print(f"Using CAN filter: {self.can_filter}")
        else:
            # Default: NO filters - capture everything (that's the point!)
            # Optimized settings (ATL0, ATS0) help reduce buffer usage
            print("No filters - capturing ALL CAN traffic (ATL0/ATS0 reduce buffer load)")

        for cmd in init_commands:
            await self._write(cmd)
            await asyncio.sleep(0.3)
            response = self._drain_queue()
            print(f"  {cmd} -> {response[:50]}...")

    async def start_monitoring(self, use_atma: bool = True) -> None:
        """Put ELM327 into monitor mode.

        Args:
            use_atma: If True, use ATMA (monitor all). If False, use ATMR (filtered).
        """
        if use_atma:
            print("\nStarting passive CAN monitoring (ATMA)...")
            await self._write("ATMA")
        else:
            print("\nStarting filtered CAN monitoring (ATMR)...")
            await self._write("ATMR")  # Monitor receive - respects CAN filters
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
    monitor = BleCANMonitor(
        args.ble,
        use_filters=bool(args.can_filter),
        can_filter=args.can_filter
    )
    log_path = Path(args.output) / f"passive_ble_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        await monitor.connect()
        await monitor.start_monitoring(use_atma=not args.use_atmr)

        print(f"\nCapturing CAN frames for {args.duration} seconds...")
        print(f"Writing to: {log_path}")
        print("Press Ctrl+C to stop early\n")

        start_time = time.time()
        frame_count = 0
        error_count = 0
        buffer_full_count = 0

        with open(log_path, 'w', encoding='utf-8') as log_file:
            log_file.write(f"# Passive Car-CAN capture via BLE\n")
            log_file.write(f"# Device: {args.ble}\n")
            log_file.write(f"# Filters: {args.can_filter if args.can_filter else 'NONE (capturing all traffic)'}\n")
            log_file.write(f"# Mode: {'ATMR (filtered)' if args.use_atmr else 'ATMA (monitor all)'}\n")
            log_file.write(f"# Started: {datetime.now().isoformat()}\n")
            log_file.write(f"# Format: <timestamp> <can_id> <data_bytes>\n\n")

            while time.time() - start_time < args.duration:
                frames = monitor.read_frames()

                for frame in frames:
                    timestamp = time.time()
                    log_file.write(f"{timestamp:.6f} {frame}\n")
                    log_file.flush()
                    frame_count += 1

                    # Print to console if enabled
                    if args.print_frames:
                        print(f"{timestamp:.6f} {frame}")

                    # Track errors
                    if "DATA ERROR" in frame or "<DATA" in frame:
                        error_count += 1
                    if "BUFFER FULL" in frame:
                        buffer_full_count += 1
                        print(f"WARNING: Buffer overflow detected at {frame_count} frames!")

                    if frame_count % 100 == 0 and not args.print_frames:
                        elapsed = time.time() - start_time
                        print(f"Captured {frame_count} frames ({error_count} errors, {buffer_full_count} overflows) "
                              f"in {elapsed:.1f}s ({frame_count/elapsed:.1f} fps)")

                await asyncio.sleep(0.01)  # Small delay to prevent busy loop

        await monitor.stop_monitoring()

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        await monitor.close()

    print("\n=== Capture Summary ===")
    print(f"Total frames: {frame_count}")
    print(f"Data errors: {error_count}")
    print(f"Buffer overflows: {buffer_full_count}")
    print(f"Success rate: {((frame_count - error_count) / frame_count * 100) if frame_count > 0 else 0:.1f}%")
    print(f"Log saved to: {log_path}")


def capture_serial(args) -> None:
    """Capture CAN frames via serial adapter."""
    monitor = SerialCANMonitor(
        args.port,
        use_filters=bool(args.can_filter),
        can_filter=args.can_filter
    )
    log_path = Path(args.output) / f"passive_serial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        monitor.connect()
        monitor.start_monitoring(use_atma=not args.use_atmr)

        print(f"\nCapturing CAN frames for {args.duration} seconds...")
        print(f"Writing to: {log_path}")
        print("Press Ctrl+C to stop early\n")

        start_time = time.time()
        frame_count = 0
        error_count = 0
        buffer_full_count = 0

        with open(log_path, 'w', encoding='utf-8') as log_file:
            log_file.write("# Passive Car-CAN capture via Serial\n")
            log_file.write(f"# Port: {args.port}\n")
            log_file.write(f"# Filters: {args.can_filter if args.can_filter else 'NONE (capturing all traffic)'}\n")
            log_file.write(f"# Mode: {'ATMR (filtered)' if args.use_atmr else 'ATMA (monitor all)'}\n")
            log_file.write(f"# Started: {datetime.now().isoformat()}\n")
            log_file.write("# Format: <timestamp> <can_id> <data_bytes>\n\n")

            last_debug = 0
            while time.time() - start_time < args.duration:
                frames = monitor.read_frames()

                # Debug: print raw buffer status every 5 seconds if no frames
                current_time = time.time() - start_time
                if frame_count == 0 and current_time - last_debug >= 5:
                    if monitor._serial:
                        waiting = monitor._serial.in_waiting
                        print(f"DEBUG: {waiting} bytes in buffer, {frame_count} frames captured so far")
                        if waiting > 0:
                            # Read a bit to see what's there
                            peek = monitor._serial.read(min(100, waiting))
                            print(f"DEBUG: Buffer peek: {peek}")
                            # Don't consume it - we'll let read_frames handle it
                    last_debug = current_time

                for frame in frames:
                    timestamp = time.time()
                    log_file.write(f"{timestamp:.6f} {frame}\n")
                    log_file.flush()
                    frame_count += 1

                    # Print to console if enabled
                    if args.print_frames:
                        print(f"{timestamp:.6f} {frame}")

                    # Track errors
                    if "DATA ERROR" in frame or "<DATA" in frame:
                        error_count += 1
                    if "BUFFER FULL" in frame:
                        buffer_full_count += 1
                        print(f"WARNING: Buffer overflow detected at {frame_count} frames!")

                    if frame_count % 100 == 0 and not args.print_frames:
                        elapsed = time.time() - start_time
                        print(f"Captured {frame_count} frames ({error_count} errors, {buffer_full_count} overflows) "
                              f"in {elapsed:.1f}s ({frame_count/elapsed:.1f} fps)")

                time.sleep(0.01)

        monitor.stop_monitoring()

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        monitor.close()

    print("\n=== Capture Summary ===")
    print(f"Total frames: {frame_count}")
    print(f"Data errors: {error_count}")
    print(f"Buffer overflows: {buffer_full_count}")
    print(f"Success rate: {((frame_count - error_count) / frame_count * 100) if frame_count > 0 else 0:.1f}%")
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
  # Scan for BLE adapter and capture ALL traffic (default - no filters)
  python scripts/capture_passive_can.py --scan --duration 60

  # Bluetooth Classic (OBDLink MX+, etc) - pair first, then find port:
  #   macOS: ls /dev/cu.*
  #   Linux: ls /dev/rfcomm*
  python scripts/capture_passive_can.py --port /dev/cu.OBDLINK-SPP --duration 60

  # Capture with custom CAN filter (only messages with ID 0x1DB)
  python scripts/capture_passive_can.py --ble AA:BB:CC:DD:EE:FF --filter 1DB

  # Use ATMR (filtered monitoring) for better compatibility
  python scripts/capture_passive_can.py --scan --duration 60 --use-atmr

  # Capture to custom output directory
  python scripts/capture_passive_can.py --port /dev/cu.OBDLINK-SPP --output ./my_logs
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

    # Filter options
    parser.add_argument('--filter', dest='can_filter', type=str, default=None,
                       help='ONLY use a filter for specific CAN ID (hex, e.g., 1DB). Default: NO filters (capture everything)')
    parser.add_argument('--use-atmr', action='store_true',
                       help='Use ATMR (filtered monitoring) instead of ATMA (monitor all)')

    # Output options
    parser.add_argument('--print', dest='print_frames', action='store_true',
                       help='Print frames to console in real-time (in addition to log file)')

    # Set defaults
    parser.set_defaults(use_filters=False, print_frames=True)

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
