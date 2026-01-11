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
