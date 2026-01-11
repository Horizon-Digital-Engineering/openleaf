# OpenLeaf Project Context

**Last Updated:** 2026-01-10 (Session 2)

## Current Status: Working with Real Car!

The BLE OBD2 adapter is now successfully reading data from a 2013 Leaf. After extensive debugging, we achieved **43.6% field coverage** (17/39 fields populated).

### Latest Test Results (2026-01-10 22:53)

| Metric | Value | Source |
|--------|-------|--------|
| SOH | 44% | Broadcast 0x5B3 |
| GIDs | 85 (~6.8 kWh) | Broadcast 0x5B3 |
| Battery HX | 60.9% | UDS Group 1 |
| Cell Voltages | 96 cells (3.976V - 3.994V) | UDS Group 2 |
| Cell Delta | 18mV | Calculated |
| Pack Temp | 22.3°C | UDS Group 4 |
| Range | 78.6 km | Broadcast 0x5A9 |
| Balancing | Active | UDS Group 6 |

### Key Fixes This Session

1. **Flow Control** - Added ATFCSH/ATFCSD/ATFCSM1 commands for multi-frame ISO-TP
2. **Byte Offsets** - Fixed Group 1, 3, 4 offsets based on raw hex analysis
3. **Broadcast Monitoring** - Added ATCRA filtering to prevent adapter overflow
4. **YAML-Driven Decoding** - Refactored to eliminate all hardcoded byte positions

See [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md) for the full debugging journey.

## Project Architecture

### Transport Layer
- **[openleaf/transports/obd2_unified.py](openleaf/transports/obd2_unified.py)** - Main transport with BLE/Serial support
- **[openleaf/transports/elm327.py](openleaf/transports/elm327.py)** - ELM327 protocol handler (ISO-TP, Flow Control, Broadcast)
- **[openleaf/transports/connections/](openleaf/transports/connections/)** - BLE/Serial connection implementations

### State Management
- **[openleaf/state.py](openleaf/state.py)** - LeafState dataclass (35+ fields) + StateStore (thread-safe)

### YAML Definitions (3 Generations)
- **[pids/leaf_aze0.yaml](pids/leaf_aze0.yaml)** - 2013-2017 (24/30kWh) - **YOUR CAR**
- **[pids/leaf_ze0.yaml](pids/leaf_ze0.yaml)** - 2011-2012 (24kWh)
- **[pids/leaf_ze1.yaml](pids/leaf_ze1.yaml)** - 2018+ (40/62kWh)

Each YAML now has:
- `metadata` - Generation, years, battery specs
- `broadcast_frames` - Passive CAN monitoring (SOH, SOC, GIDs, etc.)
- `query_pids` - Active UDS Service 0x21 queries

### API Layer
- **[openleaf/server.py](openleaf/server.py)** - FastAPI server (port 8000)

## Your 2013 Leaf Data

| Metric | Value |
|--------|-------|
| Generation | AZE0 (2013-2017) |
| Battery | 24kWh AESC LMO |
| SOH | 44% |
| Remaining Capacity | ~85 GIDs = 6.8 kWh |
| HX (Internal Resistance) | 60.9% |

## What's Working

- BLE/Serial connections
- ELM327 protocol with ISO-TP flow control
- Active PID queries (Service 0x21 Groups 1-4, 6)
- Passive broadcast monitoring (0x5B3, 0x5A9)
- All 96 cell voltages with correct scaling
- Temperature sensors (4 thermistors)
- YAML-driven signal decoding (no hardcoded offsets)

## What's Missing

- **pack_voltage, pack_current** - 0x1DB broadcast (not captured yet)
- **soc_display, soc_precise** - Need 0x5BC/0x55B captures
- **Motor/inverter data** - Only while driving
- **Charger data** - Only while charging
- **UI screens** - Cells, health, DTC displays

## Quick Start

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install pyyaml bleak pyserial

# Test connection (car must be ON)
python3 test_connection.py

# Review results
cat test_results.json | python3 -m json.tool
```

## Code Quality

The codebase is structured for reuse with any Leaf generation:

1. **YAML-driven** - All signal definitions in YAML files
2. **No hardcoded offsets** - `decode_pid_response()` and `decode_broadcast_frame()` are generic
3. **Pluggable transports** - BLE/Serial use same OBD2Transport class
4. **Easy to add cars** - Just create a new YAML and point config at it

## Key Documentation

- [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md) - Debugging journey and solutions
- [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) - Feature checklist
- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) - Full feature spec
- [docs/ref/](docs/ref/) - DBC files and CAN analysis

## Next Steps

1. **Capture more broadcast messages** - Drive/charge to get 0x1DB, 0x1DA, 0x380
2. **Expand UI** - Add cell voltage display, health screen
3. **Add logging** - Record trips for analysis
4. **Test other generations** - Verify ZE0/ZE1 YAML files

## Known Quirks

- **Car must be ON** - Broadcast messages only transmit with ignition on
- **Cheap adapters need CAN filtering** - ATCRA prevents buffer overflow
- **Temp sensor 3 returns 255** - Not present on all packs (normal)
- **Group 1 SOH/SOC unreliable** - Use broadcast 0x5B3 instead
