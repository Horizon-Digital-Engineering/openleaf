# OpenLeaf Project Context

**Last Updated:** 2026-01-11 (Session 3)

## Current Status: Full UI Working!

The Kivy UI is now displaying live data from the 2013 Leaf via BLE OBD2 adapter. All major battery metrics are working.

### Live Data (2026-01-11)

| Metric | Value | Source |
|--------|-------|--------|
| SOC | ~70% | Calculated from GIDs |
| SOH | 44% | Broadcast 0x5B3 |
| GIDs | 86 (~6.9 kWh) | Broadcast 0x5B3 |
| Battery HX | 60.9% | UDS Group 1 |
| Cell Voltages | 96 cells (3.973V - 3.994V) | UDS Group 2 |
| Cell Delta | 21mV | Calculated |
| Pack Temp | 22.3°C | UDS Group 4 |
| Range | 60 km / 37 mi | Broadcast 0x5A9 |
| Balancing | Active | UDS Group 6 |

### Session 3 Fixes

1. **Server Entry Point** - Added `main()` to server.py so `python -m openleaf.server` works
2. **SOC Calculation** - Calculate from GIDs since 0x55B/0x1DB are on EV-CAN (not accessible via OBD2)
3. **Range Fix** - Corrected bit extraction using OVMS formula from DBC reference
4. **Cell Graph** - Added Y-axis voltage labels, X-axis cell numbers, minimum bar height
5. **Debug Log Fix** - UI now handles string format debug entries

### Key Discovery: EV-CAN vs Car-CAN

The OBD2 port only exposes **Car-CAN**. Some messages are on **EV-CAN** and not accessible:
- 0x1DB (pack voltage/current, soc_display) - **EV-CAN only**
- 0x55B (soc_precise) - **EV-CAN only**

Workaround: Calculate SOC from GIDs: `soc = gids / (281 * soh/100) * 100`

## Quick Start

```bash
# Start everything (creates venv, installs deps, runs server + UI)
./start.sh all

# Or separately:
./start.sh server  # API at http://localhost:8000/state
./start.sh ui      # Kivy dashboard

# Stop
./stop.sh all
```

## Project Architecture

### Transport Layer
- **[openleaf/transports/obd2_unified.py](openleaf/transports/obd2_unified.py)** - Main transport with BLE/Serial support
- **[openleaf/transports/elm327.py](openleaf/transports/elm327.py)** - ELM327 protocol handler (ISO-TP, Flow Control, Broadcast)
- **[openleaf/transports/connections/](openleaf/transports/connections/)** - BLE/Serial connection implementations

### State Management
- **[openleaf/state.py](openleaf/state.py)** - LeafState dataclass (35+ fields) + StateStore (thread-safe)

### UI Layer
- **[openleaf/ui/kivy/main.py](openleaf/ui/kivy/main.py)** - Main Kivy app, fetches /state API
- **[openleaf/ui/kivy/ui.kv](openleaf/ui/kivy/ui.kv)** - UI layout (Dashboard, Cells, Debug screens)
- **[openleaf/ui/kivy/widgets/](openleaf/ui/kivy/widgets/)** - Custom widgets (Gauge, Metric, CellGraph)

### YAML Definitions (3 Generations)
- **[pids/leaf_aze0.yaml](pids/leaf_aze0.yaml)** - 2013-2017 (24/30kWh) - **YOUR CAR**
- **[pids/leaf_ze0.yaml](pids/leaf_ze0.yaml)** - 2011-2012 (24kWh)
- **[pids/leaf_ze1.yaml](pids/leaf_ze1.yaml)** - 2018+ (40/62kWh)

### API Layer
- **[openleaf/server.py](openleaf/server.py)** - FastAPI server (port 8000)

## Your 2013 Leaf Data

| Metric | Value |
|--------|-------|
| Generation | AZE0 (2013-2017) |
| Battery | 24kWh AESC LMO |
| SOH | 44% |
| Remaining Capacity | ~86 GIDs = 6.9 kWh |
| HX (Internal Resistance) | 60.9% |

## What's Working

- BLE/Serial connections
- ELM327 protocol with ISO-TP flow control
- Active PID queries (Service 0x21 Groups 1-4, 6)
- Passive broadcast monitoring (0x5B3, 0x5A9)
- All 96 cell voltages with correct scaling
- Temperature sensors (4 thermistors)
- YAML-driven signal decoding (no hardcoded offsets)
- **Full Kivy UI with Dashboard, Cells, Debug screens**
- **Cell voltage graph with axis labels**
- **SOC calculated from GIDs**

## What's Missing

- **pack_voltage, pack_current** - On EV-CAN, need gateway or direct CAN tap
- **Motor/inverter data** - Only available while driving
- **Charger data** - Only available while charging
- **Unit conversion toggle** - km/miles, C/F preferences

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

1. **Capture more broadcast messages** - Drive/charge to capture 0x1DA, 0x380, 0x5BC
2. **Add unit preferences** - km/miles, C/F toggle in settings
3. **Add logging** - Record trips for analysis
4. **Test other generations** - Verify ZE0/ZE1 YAML files

## Known Quirks

- **Car must be ON** - Broadcast messages only transmit with ignition on
- **Cheap adapters need CAN filtering** - ATCRA prevents buffer overflow
- **Temp sensor 3 returns 255** - Not present on all packs (normal)
- **SOC from EV-CAN unavailable** - Use calculated SOC from GIDs instead
