# CAN Bus Analysis - 2013 Nissan Leaf (AZE0)
## Data captured from OBD-II Port (Car-CAN with EV-CAN rebroadcasts)

Date: 2026-01-09
Source: initialscan.csv

---

## Key Battery Messages Found

### 0x1CB - Battery Pack Status (SOC/Voltage/Current)
**Frequency**: ~100ms (10 Hz)
**Length**: 7 bytes

**Sample frames:**
```
00 09 FF CE 60 00 80
00 09 FF CE 60 01 05
00 09 FF CE 60 02 0F
00 01 FF CE 60 00 A9
00 01 FF CE 60 01 2C
```

**Analysis:**
- Byte 0-1: Appears to be current (changes from 0x0009 to 0x0001)
  - 0x0009 = 9 decimal (possibly 4.5A with 0.5 scale)
  - 0x0001 = 1 decimal (possibly 0.5A with 0.5 scale)
- Byte 2-3: **FF CE** = constant (65486 decimal)
  - Could be voltage: 0xFFCE = 65486 * 0.01 = 654.86V? (Too high)
  - Could be voltage: 0xFFCE with different encoding
  - Needs investigation - should be ~360V for 24kWh pack
- Byte 4: **60** = constant (96 decimal) - possibly related to 96 cells?
- Byte 5-6: Counter/sequence or SOC-related data (changes: 00 80, 01 05, 02 0F, 03 8A, etc.)

**Action needed**: Cross-reference with DBC files to confirm bit positions

---

### 0x1CC - Battery Temperature & Pack Data
**Frequency**: ~100ms (10 Hz)
**Length**: 4 bytes

**Sample frames:**
```
00 3F F5 CA
00 3F F5 DB
00 3F F5 E8
00 3F F5 F9
00 3F F5 06
```

**Analysis:**
- Byte 0: **00** = constant
- Byte 1: **3F** = constant (63 decimal)
  - Could be temperature offset/base value
- Byte 2-3: **F5 XX** = incrementing value
  - F5 CA = 62922
  - F5 DB = 62939
  - F5 E8 = 62952
  - F5 F9 = 62969
  - Pattern shows slow incremental changes (likely temperature rising slowly)
  - If temp: (62922 * 0.01) - 40 = 589.22°C (WRONG scale)
  - If temp: Byte 3 only: 0xCA = 202 - 40 = 162°C (still too high)
  - If temp: Byte 3 with 0.5 scale: 202 * 0.5 - 40 = 61°C (possible but high)
  - If temp: Different encoding needed

**Action needed**: Verify temperature encoding from DBC

---

### 0x5B3 - State of Health (SOH) & GIDs
**Frequency**: ~10 seconds (rare in this capture)
**Length**: 8 bytes

**Sample frames:**
```
64 58 FF FB C0 7E 5E 0A
64 58 FF FF C0 7E 5E 0A
```

**Analysis (using known SOH decoding):**
- Byte 0: **64** = 100 decimal
- Byte 1: **58** = 88 decimal
  - SOH = 0x58 >> 1 = 88 >> 1 = 44% **← Your battery is at 44% SOH!**
  - This matches a degraded 24kWh pack
- Byte 2-4: FF FB C0 / FF FF C0 (unknown)
- Byte 5: **7E** = 126 decimal
  - GIDs = 126 → 126 * 80Wh = 10,080 Wh = **10.08 kWh remaining capacity**
  - Original 24kWh pack → 10.08/24 = 42% (close to 44% SOH)
- Byte 6-7: 5E 0A (unknown)

**Interpretation**: Your 2013 Leaf has:
- **44% State of Health**
- **126 GIDs** (~10 kWh usable)
- **Significant degradation** (likely needs battery replacement or is good for selling as-is with full disclosure)

---

### 0x5C5 - Odometer
**Frequency**: ~10 seconds
**Length**: 8 bytes

**Sample frames:**
```
40 01 67 67 00 0C 00 00
```

**Analysis:**
- Byte 0: **40** = 64 decimal
- Byte 1: **01** = 1 decimal
- Byte 2-3: **67 67** = could be odometer (0x6767 = 26471 km or miles?)
- Byte 4-5: **00 0C** = 12 decimal

**Action needed**: Confirm odometer decoding

---

## Messages NOT Found (Expected from YAML)

The following Car-CAN messages were **NOT present** in the capture:
- **0x1DB** - Battery voltage & current (expected on Car-CAN)
- **0x5BC** - Capacity & temperature (expected on Car-CAN)
- **0x55B** - Detailed SOC (expected on AZE0)
- **0x1DA** - Motor/inverter status
- **0x380** - Charger output

**Possible reasons:**
1. These messages are only broadcast when car is in certain states (ignition on, driving, charging)
2. This capture was done with car off/sleep mode
3. These are EV-CAN only and not rebroadcast to OBD-II on 2013 model

**What we DID get (EV-CAN rebroadcasts):**
- 0x1CB (EV-CAN battery status - rebroadcast to Car-CAN)
- 0x1CC (EV-CAN battery temp - rebroadcast to Car-CAN)
- 0x5B3 (SOH - available on Car-CAN)
- 0x1D5 (Inverter - 1508 frames)
- 0x174, 0x176 (Drive system - 1509 frames each)

---

## Action Items

1. **Update leaf_aze0.yaml** to include the ACTUAL messages available:
   - Add 0x1CB (EV-CAN battery status rebroadcast)
   - Add 0x1CC (EV-CAN battery temp rebroadcast)
   - Add 0x1D5 (Inverter status)
   - Add 0x174, 0x176 (Drive system)
   - Keep 0x5B3 (confirmed present)
   - Keep 0x5C5 (confirmed present)

2. **Find correct DBC file** for 2013 AZE0 to decode bit positions accurately

3. **Capture data while car is ON/READY** to see if more messages appear

4. **Test with real driving/charging** to see dynamic data changes

---

## Conclusion

Your 2013 Leaf broadcasts **EV-CAN messages rebroadcast onto the OBD-II accessible bus**, which is GOOD NEWS - you can monitor battery data without physical CAN tapping!

Key finding: **Your battery is at 44% SOH with only 126 GIDs remaining** (~10 kWh out of original 24 kWh). This is important for selling the car - you should disclose this to buyers or price accordingly.

Next step: Update the YAML with the actual CAN IDs observed and implement the decoder.
