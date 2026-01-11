# OpenLeaf Transport Architecture

## Overview

OpenLeaf uses a pluggable transport system to get vehicle data from different sources:

1. **OBD2 Transport** - Real hardware via OBD2 port
2. **Synthetic Transport** - Fake data for testing
3. **Playback Transport** - Replay recorded sessions

## OBD2 Transport

The OBD2 transport supports multiple connection types to ELM327 adapters:

- **BLE** - Bluetooth Low Energy (e.g., LELink2, Vgate iCar)
- **Serial** - USB adapters (e.g., ELM327 USB)
- **Bluetooth Classic** - via rfcomm (e.g., standard Bluetooth OBD2)

### Architecture

```
OBD2Transport
├── Connection Layer (handles I/O)
│   ├── BLEConnection - async BLE via Bleak
│   └── SerialConnection - serial/USB via pyserial
└── Protocol Layer (handles ELM327)
    └── ELM327Protocol - AT commands, ISO-TP parsing
```

### Configuration

```yaml
transport:
  type: "obd2"
  connection_type: "ble"  # or "serial" for USB/Bluetooth Classic

  # BLE settings
  ble_address: "AA:BB:CC:DD:EE:FF"

  # Serial settings
  serial_port: "/dev/ttyUSB0"
  serial_baudrate: 115200
```

## Benefits of New Architecture

1. **No Code Duplication** - Shared ELM327 protocol handler
2. **Pluggable Connections** - Easy to add WiFi, CAN, etc.
3. **Clean Separation** - I/O vs Protocol logic
4. **Recording/Playback** - Built-in session recording
5. **Unified Configuration** - One transport, multiple connections

## File Structure

```
openleaf/transports/
├── base.py              # Transport interface
├── obd2_unified.py      # Main OBD2 transport
├── synthetic.py         # Fake data generator
├── playback.py          # Session replay
├── elm327.py           # Shared protocol handler
└── connections/
    ├── base.py         # Connection interface
    ├── ble.py          # BLE connection
    └── serial.py       # Serial/USB connection
```