#!/usr/bin/env python3
"""Quick BLE scanner/inspector to find ELM327-style adapters."""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

try:
    from bleak import BleakClient, BleakScanner
except ModuleNotFoundError:
    raise SystemExit("bleak is required: pip install bleak") from None


async def scan(timeout: float, name_filter: Optional[str]) -> None:
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for address, (device, adv_data) in devices.items():
        name = device.name or adv_data.local_name or "(no name)"
        if name_filter and name_filter.lower() not in name.lower():
            continue
        rssi = adv_data.rssi
        rssi_str = f"{rssi}" if rssi is not None else "n/a"
        print(f"{device.address:40}  {name:25}  RSSI={rssi_str}")


async def inspect(address: str) -> None:
    print(f"Connecting to {address} for service inspection...")
    async with BleakClient(address) as client:
        for svc in client.services:
            print(f"Service {svc.uuid}")
            for ch in svc.characteristics:
                props = ",".join(ch.properties)
                print(f"  Char {ch.uuid} [{props}]")


def main() -> None:
    parser = argparse.ArgumentParser(description="BLE scanner for ELM327 adapters")
    parser.add_argument("--timeout", type=float, default=5.0, help="scan duration in seconds")
    parser.add_argument("--name", dest="name_filter", help="filter by substring in device name")
    parser.add_argument(
        "--inspect", dest="inspect_addr", help="after scanning, inspect services for this address"
    )
    args = parser.parse_args()

    try:
        asyncio.run(scan(args.timeout, args.name_filter))
    except Exception as exc:
        raise SystemExit(f"Scan failed: {exc}. Is Bluetooth enabled?") from exc
    if args.inspect_addr:
        asyncio.run(inspect(args.inspect_addr))


if __name__ == "__main__":
    main()
