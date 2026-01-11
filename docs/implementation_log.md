# OpenLeaf Implementation Log

This document captures the debugging journey and solutions found while getting OpenLeaf working with a cheap BLE OBD2 adapter on a 2013 Nissan Leaf.

---

## Session: 2026-01-10 - BLE Adapter Debugging

### Hardware
- **Car**: 2013 Nissan Leaf AZE0 (24kWh)
- **Adapter**: Generic BLE ELM327 clone (~$15)
- **Reference**: LeafSpy Pro (works with same adapter)

### Starting Point
- BLE connection established via `bleak` library
- ELM327 handshake working (ATZ, ATI, etc.)
- UDS Service 0x21 queries returning data
- **Problem**: All decoded values were wrong (SOH showing 6.46% instead of 44%)

---

## Issue 1: BLE Write Not Working

**Symptom**: Commands sent but no response received.

**Root Cause**: Using `response=False` in BLE write, which doesn't wait for acknowledgment.

**Fix** in [openleaf/transports/connections/ble.py](../openleaf/transports/connections/ble.py):
```python
# Before (broken)
await self._client.write_gatt_char(self.write_char_uuid, data, response=False)

# After (working)
await self._client.write_gatt_char(self.write_char_uuid, data, response=True)
```

---

## Issue 2: Multi-Frame ISO-TP Responses Not Working

**Symptom**: Only getting First Frame, no Consecutive Frames.

**Root Cause**: Cheap ELM327 clones don't auto-send Flow Control frames. Need manual FC configuration.

**Solution**: Send Flow Control setup commands before each PID query.

**Fix** in [openleaf/transports/elm327.py](../openleaf/transports/elm327.py):
```python
def query_pid(self, pid: PidDefinition) -> bytes:
    # Configure flow control for multi-frame responses
    self.send_command(f"ATFCSH{pid.request_id:03X}")  # FC header
    self.send_command("ATFCSD300000")  # FC data: 30=CTS, 00=no limit, 00=no delay
    self.send_command("ATFCSM1")  # Enable user-defined FC mode

    self.send_command(f"ATSH{pid.request_id:03X}")
    # ... rest of query
```

**Key AT Commands**:
- `ATFCSH79B` - Set Flow Control header to 0x79B (LBC ECU)
- `ATFCSD300000` - Set FC data: 0x30 = Continue To Send, 0x00 = unlimited blocks, 0x00 = no delay
- `ATFCSM1` - Enable user-defined Flow Control mode

---

## Issue 3: Group 1 Byte Offsets Wrong

**Symptom**: `soc_true` showing 655.35%, `soh_precise` showing 6.46%

**Root Cause**: Community documentation and YAML files had incorrect byte positions for Group 1.

**Investigation**:
- Dumped raw hex from Group 1 response
- Cross-referenced with dalathegreat/Battery-Emulator and jsphuebner/stm32-car projects
- Found that SOH and SOC in Group 1 are **unreliable** - community projects use broadcast messages instead

**Discovery**: Group 1 contains `battery_hx` (internal resistance health) at bytes 16-17.

**Fix** in [pids/leaf_aze0.yaml](../pids/leaf_aze0.yaml):
```yaml
# Changed from wrong SOH/SOC to correct battery_hx
- key: "battery_hx"
  byte_offset: 16
  byte_length: 2
  scale: 0.009765625  # 1/102.4
  description: "Battery HX (internal resistance health factor)"
```

**Result**: `battery_hx: 60.9%` correlates correctly with 44% SOH battery.

---

## Issue 4: Group 3 Cell Voltage Offsets Wrong

**Symptom**: `cell_v_min` and `cell_v_max` showing 65.535V (impossible for 3.8V cells)

**Root Cause**: Wrong byte offsets in YAML - legacy documentation error.

**Investigation**: Analyzed raw hex dump:
```
Raw Group 3: FF FF 0A 07 ... 0F 92 0F 88 ...
                           ^    ^    ^    ^
                       byte 10-11  12-13
                       = 0F92     = 0F88
                       = 3.986V   = 3.976V
```

**Fix** in [pids/leaf_aze0.yaml](../pids/leaf_aze0.yaml):
```yaml
- key: "cell_v_max"
  byte_offset: 10  # Was 0
  byte_length: 2
  scale: 0.001

- key: "cell_v_min"
  byte_offset: 12  # Was 2
  byte_length: 2
  scale: 0.001
```

---

## Issue 5: Broadcast Messages Not Captured

**Symptom**: `ATMA` (Monitor All) command causes adapter to buffer overflow and hang.

**Root Cause**: Cheap adapters can't handle high-frequency CAN traffic (10+ messages/second).

**Solution**: Use `ATCRA` to filter specific CAN IDs before monitoring.

**Fix** in [openleaf/transports/elm327.py](../openleaf/transports/elm327.py):
```python
def monitor_broadcast(self, can_ids: List[int], duration_sec: float) -> Dict[int, bytes]:
    for can_id in can_ids:
        self.send_command("ATCAF0")  # Raw frames
        self.send_command(f"ATCRA{can_id:03X}")  # Filter to this ID only
        self.connection.send_sync("ATMA")  # Start monitoring
        # ... capture with timeout ...

    self.send_command("ATAR")  # Reset CAN filters
    self.send_command("ATCAF1")  # Re-enable CAN formatting
```

**Key Discovery**: SOH and SOC come from **broadcast messages**, not UDS queries:
- `0x5B3` byte 1: SOH (bit-shifted: `data[1] >> 1`)
- `0x5B3` byte 5: GIDs (stored energy)
- `0x5BC`: Charge bars, pack temp
- `0x55B`: Precise SOC (10-bit)

---

## Issue 6: Broadcast Requires Car ON

**Symptom**: 0x5B3 and other broadcast messages not appearing.

**Root Cause**: Broadcast messages only transmitted when ignition is ON.

**Solution**: Test with car in READY mode (not just accessory).

---

## Issue 7: Hardcoded Byte Offsets in Broadcast Decoder

**Symptom**: Code had hardcoded `data[1] >> 1` for SOH instead of using YAML.

**Root Cause**: Quick debugging hack became permanent code.

**Solution**: Created YAML-driven broadcast decoder matching the PID decoder pattern.

**New Components**:
1. `BroadcastFrame` dataclass in [elm327.py](../openleaf/transports/elm327.py)
2. `decode_broadcast_frame()` function with formula support
3. Loader in `_load_definitions()` that parses `broadcast_frames` from YAML
4. Updated `poll_broadcast_messages()` to use loaded definitions

**Result**: Broadcast decoding is now fully data-driven. Adding new CAN IDs only requires YAML changes.

---

## Final Results

**Test Run (2026-01-10 22:53)**:
- **17 fields populated** out of 38 defined
- **43.6% coverage** (up from ~20% at start)

**Working Fields**:
| Field | Value | Source |
|-------|-------|--------|
| soh_alt | 44% | Broadcast 0x5B3 |
| gids | 85 (~6.8 kWh) | Broadcast 0x5B3 |
| battery_hx | 60.9% | UDS Group 1 |
| cell_voltages | 96 cells | UDS Group 2 |
| cell_v_max | 3.994V | UDS Group 3 |
| cell_v_min | 3.976V | UDS Group 3 |
| cell_v_delta | 18mV | Calculated |
| temp_sensor_1 | 22°C | UDS Group 4 |
| temp_sensor_2 | 23°C | UDS Group 4 |
| temp_sensor_3 | 255 (N/A) | UDS Group 4 |
| temp_sensor_4 | 22°C | UDS Group 4 |
| pack_temp_c | 22.3°C | Calculated |
| balancing_active | 1 (on) | UDS Group 6 |
| range_km | 78.6 | Broadcast 0x5A9 |

**Not Working (Need Investigation)**:
- `pack_voltage`, `pack_current` - From 0x1DB (not captured yet)
- `soc_display`, `soc_precise` - Need more broadcast captures
- Motor/inverter data - Only active while driving
- Charger data - Only active while charging

---

## Key Learnings

1. **Cheap ELM327 clones need manual Flow Control** - Use ATFCSH/ATFCSD/ATFCSM1
2. **Community documentation has errors** - Always verify byte offsets against raw data
3. **SOH/SOC are in broadcast messages, not UDS** - Group 1 is unreliable for these
4. **CAN filtering is essential** - ATCRA prevents buffer overflow on cheap adapters
5. **YAML-driven architecture pays off** - Easy to fix offsets without code changes
6. **Car must be ON** - Broadcast messages only transmit with ignition on

---

## Architecture After Refactoring

```
YAML Definitions (pids/leaf_*.yaml)
        │
        ├── broadcast_frames: [{id: 0x5B3, signals: [...]}]
        │
        └── query_pids: [{request_id: 0x79B, signals: [...]}]
                │
                ▼
    OBD2Transport._load_definitions()
        │
        ├── self.broadcast_frames: Dict[int, BroadcastFrame]
        │
        └── self.pids: List[PidDefinition]
                │
                ▼
    ┌───────────────────────────────────────┐
    │         ELM327Protocol                │
    │  ┌─────────────┐  ┌────────────────┐  │
    │  │ query_pid() │  │ monitor_broadcast│ │
    │  └─────────────┘  └────────────────┘  │
    └───────────────────────────────────────┘
                │
                ▼
    ┌───────────────────────────────────────┐
    │         Generic Decoders              │
    │  ┌──────────────────┐  ┌───────────┐  │
    │  │decode_pid_response│ │decode_bcast│  │
    │  └──────────────────┘  └───────────┘  │
    └───────────────────────────────────────┘
                │
                ▼
            LeafState (35+ fields)
```

**No hardcoded byte offsets in transport code** - all decoding driven by YAML.

---

## Session: 2026-01-11 - Full UI Working

### Goal
Get the full stack running with live data displayed in the Kivy UI.

---

## Issue 8: Server Won't Start

**Symptom**: `./start.sh all` runs but server log is empty, UI shows no data.

**Root Cause**: `openleaf/server.py` had no `main()` entry point or `if __name__ == "__main__"` block. Running `python -m openleaf.server` did nothing.

**Fix** in [openleaf/server.py](../openleaf/server.py):
```python
def main() -> None:
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="OpenLeaf State Server")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config file")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()

    config = load_config(args.config)
    server = LeafStateServer(config)
    server.start_background_loop()
    uvicorn.run(server.app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
```

---

## Issue 9: UI Crash on Debug Log

**Symptom**: UI crashes with `AttributeError: 'str' object has no attribute 'get'`

**Root Cause**: Debug log entries changed from dicts `{"ts": ..., "direction": ..., "data": ...}` to strings `"[4.08] pid: Battery Health Data: {'battery_hx': 60.95}"`.

**Fix** in [openleaf/ui/kivy/main.py](../openleaf/ui/kivy/main.py):
```python
def _update_debug_view(self, screen_manager, log: list) -> None:
    for entry in reversed(log):
        # Handle both string entries and dict entries
        if isinstance(entry, str):
            line = entry
        else:
            ts = entry.get("ts", 0.0)
            # ... dict handling
```

---

## Issue 10: SOC Always Shows 0%

**Symptom**: SOH shows 44%, but SOC shows 0%.

**Root Cause**: The SOC signals (`soc_display` from 0x1DB, `soc_precise` from 0x55B) are on **EV-CAN**, not **Car-CAN**. The OBD2 port only exposes Car-CAN.

**Key Discovery**:
- OBD2 port = Car-CAN only
- 0x1DB (pack voltage, current, SOC) = EV-CAN only
- 0x55B (precise SOC) = EV-CAN only
- 0x5B3 (SOH, GIDs) = Car-CAN (accessible)
- 0x5A9 (range) = Car-CAN (accessible)

**Workaround**: Calculate SOC from GIDs using the formula:
```python
# Max GIDs for 24kWh pack = 281 (new), adjusted by SOH
max_gids = 281 * (soh / 100.0)
soc = (gids / max_gids) * 100.0
```

**Fix** in [openleaf/transports/obd2_unified.py](../openleaf/transports/obd2_unified.py):
```python
def _calculate_derived_values(self, state: Dict[str, Any]) -> None:
    # ... existing code ...

    # Calculate SOC from GIDs if not available from broadcast
    if state.get("gids") and not state.get("soc_display"):
        gids = state["gids"]
        soh = state.get("soh_alt") or state.get("soh") or 100.0
        max_gids_new = 281
        max_gids = max_gids_new * (soh / 100.0)
        if max_gids > 0:
            soc = min(100.0, (gids / max_gids) * 100.0)
            state["soc_display"] = round(soc, 1)
```

**Result**: SOC now shows ~70% (86 GIDs ÷ 124 max GIDs at 44% SOH).

---

## Issue 11: Range Shows Wrong Value

**Symptom**: Range showing 104.2 km but car dash shows 37 miles (59.5 km).

**Root Cause**: YAML had wrong `start_bit: 3` for range signal. DBC file shows correct extraction method.

**Investigation**: Found in DBC reference:
```
RangeInstrumentCluster : 15|12@0+ (0.2,0) [0|819] "km"
OVMS formula: nl_range = d[1] << 4 | d[2] >> 4; m_range_instrument->SetValue(nl_range / 5, Kilometers);
```

**Fix** in [pids/leaf_aze0.yaml](../pids/leaf_aze0.yaml):
```yaml
- key: "range_km"
  start_bit: 8
  length: 12
  scale: 0.2
  unit: "km"
  formula: "(data[1] << 4) | (data[2] >> 4)"
```

Also updated [elm327.py](../openleaf/transports/elm327.py) to pass `data` to formula eval:
```python
if signal.formula:
    value = eval(signal.formula, {"value": value, "data": data})
```

**Result**: Range now shows 60 km = 37.3 miles (matches dash).

---

## Issue 12: Cell Graph Missing Cells

**Symptom**: Some cells at minimum voltage are invisible (bar height = 0).

**Root Cause**: Bar height calculated as `(value - min) / span * height`, so minimum cell gets height 0.

**Fix** in [openleaf/ui/kivy/widgets/cell_graph.py](../openleaf/ui/kivy/widgets/cell_graph.py):
```python
# Add 15% padding below min so lowest cells are still visible
padding_v = span * 0.15
display_min = min_v - padding_v
display_span = (max_v - display_min)

# Minimum bar height so lowest cell is visible
min_bar_height = dp(6)
for index, value in enumerate(self.values):
    norm = (value - display_min) / display_span
    bar_height = max(graph_height * norm, min_bar_height)
```

Also added Y-axis voltage labels and X-axis cell numbers (every 12 cells).

---

## Final Results (Session 3)

**Full UI Working with Live Data**:

| Metric | Value | Source |
|--------|-------|--------|
| SOC | ~70% | Calculated from GIDs |
| SOH | 44% | Broadcast 0x5B3 |
| GIDs | 86 | Broadcast 0x5B3 |
| HX | 60.9% | UDS Group 1 |
| Cell Voltages | 96 cells | UDS Group 2 |
| Cell Delta | 21mV | Calculated |
| Pack Temp | 22.3°C | UDS Group 4 |
| Range | 60 km / 37 mi | Broadcast 0x5A9 |
| Balancing | Active | UDS Group 6 |

**UI Features**:
- Dashboard with SOC/SOH gauges
- GIDs, HX, Range metrics
- Cell voltage graph with Y-axis labels and X-axis cell numbers
- Debug log viewer

---

## Key Learnings (Session 3)

1. **EV-CAN vs Car-CAN** - OBD2 port only exposes Car-CAN. Pack voltage/current (0x1DB) and precise SOC (0x55B) are on EV-CAN and not accessible.
2. **SOC can be calculated from GIDs** - Formula: `soc = gids / (281 * soh/100) * 100`
3. **DBC files are the source of truth** - OVMS formulas in DBC comments are reliable
4. **Always add entry points** - Python modules need `if __name__ == "__main__"` to be runnable
5. **Handle data format changes** - Debug logs changed from dicts to strings, broke UI

---

## Session: 2026-01-11 - DTC Support

### Goal
Add diagnostic trouble code (DTC) read and clear functionality.

---

## Feature: YAML-Driven ECU Definitions

**Problem**: ECU addresses vary by Leaf generation. Hardcoding them limits flexibility.

**Solution**: Add `ecus` section to YAML files with per-generation ECU definitions.

**Implementation** in [pids/leaf_aze0.yaml](../pids/leaf_aze0.yaml):
```yaml
ecus:
  - id: 0x79B
    response_id: 0x7BB
    name: "LBC"
    description: "Lithium Battery Controller"
    supports_dtc: true
  - id: 0x797
    response_id: 0x7B7
    name: "VCM"
    description: "Vehicle Control Module"
    supports_dtc: true
  # ... 8 ECUs total for AZE0
```

**ZE1 has additional ECUs**:
- ADAS (0x756) - ProPilot / Advanced Driver Assistance
- ICM (0x764) - Intelligent Cruise Module (e-Pedal)

---

## Feature: DTC Read from All ECUs

**Implementation** in [openleaf/transports/obd2_unified.py](../openleaf/transports/obd2_unified.py):

```python
@dataclass
class EcuDefinition:
    """ECU definition loaded from YAML."""
    id: int
    response_id: int
    name: str
    description: str = ""
    supports_dtc: bool = True

def read_dtcs(self) -> Dict[str, List[str]]:
    """Read DTCs from all ECUs defined in YAML."""
    results: Dict[str, List[str]] = {}
    for ecu in self.ecus:
        if not ecu.supports_dtc:
            continue
        try:
            dtcs = self.protocol.read_dtcs(ecu_id=ecu.id)
            results[ecu.name] = dtcs if dtcs else []
        except Exception as e:
            results[ecu.name] = ["ERROR"]
    return results
```

**Protocol**: UDS Service 0x19 (Read DTC) with sub-function 0x02 (reportDTCByStatusMask)

---

## Feature: DTC Clear from All ECUs

**Implementation**:
```python
def clear_dtcs(self) -> Dict[str, bool]:
    """Clear DTCs from all ECUs defined in YAML."""
    results = {}
    for ecu in self.ecus:
        if not ecu.supports_dtc:
            continue
        try:
            success = self.protocol.clear_dtcs(ecu_id=ecu.id)
            results[ecu.name] = success
        except Exception:
            results[ecu.name] = False
    return results
```

**Protocol**: UDS Service 0x14 (Clear DTC) with 0xFFFFFF for all groups

---

## Feature: Per-ECU UI Display

**Problem**: User wanted to see each ECU scanned, not just "No DTCs found".

**Solution**: Update UI to show per-ECU results with color coding.

**Implementation** in [openleaf/ui/kivy/main.py](../openleaf/ui/kivy/main.py):
```python
def _update_dtc_view(self, screen_manager, ecu_results: dict[str, list[str]]) -> None:
    for ecu_name, codes in ecu_results.items():
        if not codes:
            # Green - No DTCs
            background_color = (0.15, 0.35, 0.20, 1)
            text = f"{ecu_name}: OK"
        elif codes == ["ERROR"]:
            # Orange - ECU didn't respond
            background_color = (0.35, 0.25, 0.15, 1)
            text = f"{ecu_name}: No Response"
        else:
            # Red - Has DTCs
            background_color = (0.45, 0.18, 0.18, 1)
            text = f"{ecu_name}:{code}"
```

**Toast messages**:
- "Scanning ECUs..." when starting
- "Scanned 8 ECUs - All OK" when no DTCs
- "Found 3 DTC(s)" when DTCs present

---

## API Changes

**Endpoint**: `GET /dtcs`
```json
{
  "ecus": {
    "LBC": [],
    "VCM": ["P0A1F"],
    "ABS": [],
    "EPS": ["ERROR"],
    ...
  }
}
```

**Endpoint**: `POST /command/clear_dtcs`
```json
{
  "status": "ok",
  "results": {
    "LBC": true,
    "VCM": true,
    ...
  }
}
```

---

## Files Modified (Session 4)

| File | Changes |
|------|---------|
| pids/leaf_aze0.yaml | Added ECU definitions section |
| pids/leaf_ze0.yaml | Added ECU definitions section |
| pids/leaf_ze1.yaml | Added ECU definitions (including ADAS, ICM) |
| openleaf/transports/obd2_unified.py | EcuDefinition dataclass, read_dtcs(), clear_dtcs() |
| openleaf/server.py | Updated /dtcs endpoint to return per-ECU results |
| openleaf/ui/kivy/services/api.py | Updated read_dtcs() return type |
| openleaf/ui/kivy/main.py | Per-ECU DTC display with color coding |

---

## Key Learnings (Session 4)

1. **ECU addresses vary by generation** - ZE1 has ADAS and ICM not present in ZE0/AZE0
2. **YAML-driven is the way** - ECU definitions in YAML make generation-specific support easy
3. **Show work, not just results** - Users want to see each ECU scanned, not just "no DTCs"
4. **Color coding improves UX** - Green/Orange/Red makes scan results instantly readable
