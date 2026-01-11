# Passive CAN Capture Scripts

Two standalone scripts for capturing and analyzing passive Car-CAN broadcasts from Nissan Leaf vehicles.

## Quick Start

### 1. Capture CAN Data

Connect your ELM327 adapter and capture 60 seconds of passive CAN traffic:

```bash
# Using serial/Bluetooth rfcomm adapter
python scripts/capture_passive_can.py --port /dev/rfcomm0 --duration 60

# Using BLE adapter (LELink2, etc.)
python scripts/capture_passive_can.py --ble AA:BB:CC:DD:EE:FF --duration 120

# Custom output directory
python scripts/capture_passive_can.py --port /dev/rfcomm0 --duration 60 --output ./my_captures
```

**What it does:**
- Initializes ELM327 adapter
- Puts it into `ATMA` (monitor all) mode to passively listen
- Captures all CAN frames on Car-CAN bus (no queries sent!)
- Saves timestamped log file to `logs/passive_*.log`

**Tips:**
- Park your car and turn it ON (ready mode) before capturing
- Try capturing during different states: idle, charging, driving, climate on/off
- Longer captures (2-5 minutes) give better data for analysis

---

### 2. Parse and Decode Captured Data

Analyze the captured log to see decoded messages:

```bash
# Full analysis with decoded messages
python scripts/parse_passive_can.py logs/passive_20250123_120000.log

# Summary statistics only
python scripts/parse_passive_can.py logs/passive_20250123_120000.log --summary

# Filter to specific CAN ID
python scripts/parse_passive_can.py logs/passive_20250123_120000.log --can-id 5B3
```

**What it shows:**
- Total frames captured and capture duration
- All CAN IDs observed with frequency (messages/second)
- Decoded values for known messages (SOC, SOH, GIDs, voltage, odometer)
- Min/max/avg statistics for each signal

---

## Known Passive Messages

These messages are automatically broadcast by the Leaf ECUs on Car-CAN:

| CAN ID | Name | Signals | Description |
|--------|------|---------|-------------|
| `0x5B3` | Battery Status | SOH%, GIDs | Battery health and capacity |
| `0x5BC` | SOC Broadcast | SOC% | State of charge (dashboard display) |
| `0x1DB` | Charging Status | HV voltage, charging flag | Charging state and pack voltage |
| `0x5C5` | Odometer | Total km | Vehicle odometer |
| `0x55B` | Speed & Power | Speed (km/h) | Vehicle speed |

*More CAN IDs will be discovered during your captures!*

---

## Testing Plan

### 2013 Leaf (AZE0) Capture
```bash
# Capture during idle
python scripts/capture_passive_can.py --port /dev/rfcomm0 --duration 120 --output ./logs/aze0

# Parse results
python scripts/parse_passive_can.py logs/aze0/passive_*.log --summary
```

### 2018 Leaf (ZE1) Capture
```bash
# Capture during idle
python scripts/capture_passive_can.py --ble AA:BB:CC:DD:EE:FF --duration 120 --output ./logs/ze1

# Parse results
python scripts/parse_passive_can.py logs/ze1/passive_*.log --summary
```

### Compare Generations
After capturing from both vehicles, compare:
- Which CAN IDs are present in both vs generation-specific
- Different broadcast rates (messages/second)
- Different data byte layouts or scaling factors

---

## Expected Output Example

```
Analyzing: logs/passive_20250123_120000.log
================================================================================

Total frames parsed: 4523
Capture duration: 60.23 seconds
Average rate: 75.1 frames/second

CAN IDs observed (total: 42 unique IDs):
--------------------------------------------------------------------------------
  ✓ 0x5BC   2410 frames  ( 40.0/s)  SOC Broadcast
  ✓ 0x5B3    120 frames  (  2.0/s)  Battery Status Broadcast
  ✓ 0x1DB    602 frames  ( 10.0/s)  Charging Status
  ✓ 0x55B   1205 frames  ( 20.0/s)  Speed and Power
  ✓ 0x5C5     60 frames  (  1.0/s)  Odometer Broadcast
    0x180    301 frames  (  5.0/s)  Unknown
    0x1F2    602 frames  ( 10.0/s)  Unknown
  ... and 35 more CAN IDs

Decoded Messages:
================================================================================

0x5B3 - Battery Status Broadcast (120 frames)
  Battery SOH, GIDs, capacity
--------------------------------------------------------------------------------

  [    0.00s] Raw: 12AB34CD56EF7890
    soh_pct              =      72.00 %       # State of Health percentage
    gids                 =     180.00 GIDs    # Battery capacity in GIDs

  [   30.12s] Raw: 12AB34CD56EF7890
    soh_pct              =      72.00 %       # State of Health percentage
    gids                 =     180.00 GIDs    # Battery capacity in GIDs

0x5BC - SOC Broadcast (2410 frames)
  State of Charge percentage
--------------------------------------------------------------------------------

  [    0.02s] Raw: 02D0
    soc_pct              =      72.00 %       # State of Charge
```

---

## Next Steps

After capturing from both vehicles:

1. **Identify generation differences**: Note which CAN IDs differ between 2013 vs 2018
2. **Reverse engineer unknown IDs**: Look at unknown CAN IDs and try to correlate with vehicle behavior
3. **Update passive message definitions**: Add new discovered messages to `PASSIVE_MESSAGES` dict in parser
4. **Create generation-specific YAML configs**:
   - `pids/aze0/passive_car_can.yaml`
   - `pids/ze1/passive_car_can.yaml`

---

## Troubleshooting

**No frames captured:**
- Ensure car is in READY/ON mode (not just accessory)
- Check ELM327 adapter is properly paired/connected
- Try increasing capture duration
- Verify adapter supports protocol 6 (ISO 15765-4 CAN 500kbaud)

**Parser shows "Unknown" for all IDs:**
- This is normal for first captures - we need to discover what's broadcast
- Compare your captures with community CAN databases (dalathegreat's repo)
- Look for patterns in hex data that match known values (SOC%, speed, etc.)

**Low message rate:**
- Some messages only broadcast when relevant (charging messages when plugged in)
- Try capturing during different vehicle states
- Idle mode typically has fewer messages than driving

---

## References

- [docs/ref/leaf_can_obd_summary.md](../docs/ref/leaf_can_obd_summary.md) - Overview of Leaf CAN architecture
- [dalathegreat/leaf_can_bus_messages](https://github.com/dalathegreat/leaf_can_bus_messages) - Community DBC files
- ELM327 Data Sheet - AT command reference
