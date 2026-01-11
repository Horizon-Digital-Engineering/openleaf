# Nissan Leaf Generations Reference

Complete breakdown of all Nissan Leaf generations, variants, and their CAN bus characteristics.

---

## Generation Overview

### Gen 1: ZE0 (2010-2012)
**Years**: 2010, 2011, 2012
**Battery**: 24 kWh
**Chemistry**: AESC LMO "Canary"
**Configuration**: 96s2p (192 cells total)
**Motor**: EM61
**Max Charge Voltage**: 392V
**Features**:
- Electrical handbrake
- Original Leaf design
- Prone to rapid degradation in hot climates

**CAN Access**: Direct via OBD-II pins 12/13 (EV-CAN) and 6/14 (Car-CAN)
**DBC File**: `LEAF_2011-2017_ZE0_AZEO.dbc` or `LEAF_ZE0.dbc`

---

### Gen 2: AZE0-0 "Wolf" (Early 2013-2014)
**Years**: 2013 (before May), 2014 (early)
**Battery**: 24 kWh
**Chemistry**: AESC LMO "Wolf"
**Configuration**: 96s2p (192 cells total)
**Motor**: EM57
**Max Charge Voltage**: 396V
**Features**:
- Foot-operated handbrake (replaced electrical)
- Improved motor (EM57 vs EM61)
- Still vulnerable to heat degradation

**Battery Part Number**: 295B0-3NA0A
**CAN Access**: Direct via OBD-II pins 12/13 (EV-CAN) and 6/14 (Car-CAN)
**DBC File**: `LEAF_2011-2017_ZE0_AZEO.dbc`

---

### Gen 2.5: AZE0-1 "Lizard" (Late 2013-2015)
**Years**: 2013 (after May), 2014, 2015
**Battery**: 24 kWh
**Chemistry**: AESC LMO "Lizard" (heat-resistant)
**Configuration**: 96s2p (192 cells total)
**Motor**: EM57
**Max Charge Voltage**: 396V
**Features**:
- Foot-operated handbrake
- Heat-resistant battery chemistry
- Better degradation resistance in hot climates
- Otherwise identical to AZE0-0

**Battery Part Number**: 295B0-3NA1A (note the "1" vs "0")
**CAN Access**: Direct via OBD-II pins 12/13 (EV-CAN) and 6/14 (Car-CAN)
**DBC File**: `LEAF_2011-2017_ZE0_AZEO.dbc`
**Note**: Same CAN messages as AZE0-0 (only chemistry differs)

---

### Gen 3: AZE0-2 (2016-2017)
**Years**: 2016, 2017
**Battery**: 30 kWh
**Chemistry**: LG Chem NMC (Nickel Manganese Cobalt)
**Configuration**: 96s2p (192 cells total, larger capacity cells)
**Motor**: EM57
**Max Charge Voltage**: 396V
**Features**:
- 25% more capacity (30 kWh vs 24 kWh)
- Better chemistry (NMC vs LMO)
- Improved range (~107 miles EPA)
- Max GIDs: ~356 (vs 281 for 24kWh)

**CAN Access**: Direct via OBD-II pins 12/13 (EV-CAN) and 6/14 (Car-CAN)
**DBC File**: `LEAF_2011-2017_ZE0_AZEO.dbc`
**Note**: Same CAN protocol, different capacity values

---

### Gen 4: ZE1 40kWh (2018-2019)
**Years**: 2018, 2019, 2020, 2021, 2022
**Battery**: 40 kWh
**Chemistry**: AESC NMC
**Configuration**: 96s2p (192 cells total)
**Motor**: EM57 110kW
**Max Charge Voltage**: 404V
**Features**:
- Completely redesigned exterior (facelifted)
- ProPILOT driver assistance
- Max GIDs: ~475
- Improved range (~150 miles EPA)

**CAN Access**: **BLOCKED** - OBD-II gateway shuts down when car is off
**Workaround**: Requires 8-wire CAN tap behind instrument cluster
**DBC File**: `LEAF_2018-_ZE1.dbc`
**Note**: CAN protocol has some encryption/authentication changes

---

### Gen 5: ZE1 e+ 62kWh (2019-2023)
**Years**: 2019, 2020, 2021, 2022, 2023
**Battery**: 62 kWh
**Chemistry**: AESC NMC
**Configuration**: **96s3p** (288 cells total - 3 parallel vs 2)
**Motor**: EM57 160kW (higher power variant)
**Max Charge Voltage**: 404V
**Features**:
- Same exterior as 40kWh ZE1
- 50% more capacity
- Higher power motor (160kW vs 110kW)
- Max GIDs: ~728
- Improved range (~226 miles EPA)
- Different current sensor vs 40kWh

**CAN Access**: **BLOCKED** - Same gateway issue as 40kWh ZE1
**Workaround**: Requires 8-wire CAN tap behind instrument cluster
**DBC File**: `LEAF_2018-_ZE1.dbc`
**Note**: Still reports 96 cell pair voltages (averaged from 3p config)

---

## Summary Table

| Gen | Model Code | Years | Battery | Chemistry | Motor | Max V | Handbrake | CAN Access | Max GIDs |
|-----|------------|-------|---------|-----------|-------|-------|-----------|------------|----------|
| 1 | ZE0 | 2010-2012 | 24 kWh | LMO Canary | EM61 | 392V | Electric | Direct | 281 |
| 2 | AZE0-0 | Early 2013-2014 | 24 kWh | LMO Wolf | EM57 | 396V | Foot | Direct | 281 |
| 2.5 | AZE0-1 | Late 2013-2015 | 24 kWh | LMO Lizard | EM57 | 396V | Foot | Direct | 281 |
| 3 | AZE0-2 | 2016-2017 | 30 kWh | NMC | EM57 | 396V | Foot | Direct | 356 |
| 4 | ZE1 | 2018-2022 | 40 kWh | NMC | EM57 110kW | 404V | Foot | **Blocked** | 475 |
| 5 | ZE1 e+ | 2019-2023 | 62 kWh | NMC | EM57 160kW | 404V | Foot | **Blocked** | 728 |

---

## CAN Bus Configuration by Generation

### ZE0 & AZE0 (2010-2017)
**Access**: Direct via OBD-II, no gateway blocking

**Available Buses**:
- **Car-CAN**: Pins 6 (CAN-H) and 14 (CAN-L) on OBD-II connector
- **EV-CAN**: Pins 12 (CAN-H) and 13 (CAN-L) on OBD-II connector

**Typical Setup**:
- Most OBD-II adapters default to EV-CAN (pins 12/13)
- EV-CAN has more detailed battery data
- Some messages are rebroadcast between buses

**Baud Rate**: 500 kbps (both buses)

---

### ZE1 (2018+)
**Access**: **BLOCKED by powered gateway**

**Problem**:
- Gateway on OBD-II port shuts down when car is off
- Cannot sniff passive CAN data reliably
- Active queries may work but limited

**Workaround**:
- Build 8-wire cable (not standard 6-wire OBD cable)
- Tap CAN gateway harness behind instrument cluster
- Requires interior disassembly
- See OVMS documentation for wiring diagram

**Baud Rate**: 500 kbps

---

## How to Identify Your Leaf Generation

### Physical Inspection

**Handbrake**:
- Electric handbrake button = ZE0 (2010-2012)
- Foot-operated handbrake = AZE0 or ZE1 (2013+)

**Exterior Design**:
- Original rounded design = ZE0/AZE0 (2010-2017)
- Sharp angular design = ZE1 (2018+)

**Battery Capacity Badge**:
- No badge / "ZERO EMISSION" only = 24 kWh
- "30 kWh" badge on hatch = 30 kWh (2016-2017)
- No special badge but 2018+ = 40 kWh
- "e+ PLUS" badge = 62 kWh (2019+)

---

### Battery Part Numbers

**Under the car or in service records:**

| Part Number | Generation | Chemistry | Capacity |
|-------------|------------|-----------|----------|
| 295B0-3NA0A | AZE0-0 | LMO Wolf | 24 kWh |
| 295B0-3NA1A | AZE0-1 | LMO Lizard | 24 kWh |
| 295B0-4NA0A | AZE0-2 | NMC | 30 kWh |
| 295B0-5SA0A | ZE1 | NMC | 40 kWh |
| 295B0-5SA1A | ZE1 e+ | NMC | 62 kWh |

---

### Via CAN Data

**Read 0x5B3 (SOH message) byte 5:**

```python
# GIDs to generation mapping
gids = byte[5]
max_gids_observed = gids / current_soh

if max_gids_observed <= 290:
    generation = "24 kWh (ZE0/AZE0-0/AZE0-1)"
elif max_gids_observed <= 365:
    generation = "30 kWh (AZE0-2)"
elif max_gids_observed <= 485:
    generation = "40 kWh (ZE1)"
else:
    generation = "62 kWh (ZE1 e+)"
```

---

## DBC File Mapping

| DBC Filename | Covers | Notes |
|--------------|--------|-------|
| `LEAF_ZE0.dbc` | ZE0 (2010-2012) | Original file, may be outdated |
| `LEAF_2011-2017_ZE0_AZEO.dbc` | ZE0, AZE0-0, AZE0-1, AZE0-2 | **Recommended** for all 2010-2017 models |
| `LEAF_2018-_ZE1.dbc` | ZE1 40kWh, ZE1 e+ 62kWh | For 2018+ models |

**Download from**: https://github.com/dalathegreat/leaf_can_bus_messages

---

## Known Issues by Generation

### ZE0 "Canary" (2010-2012)
- **Rapid degradation** in hot climates (Arizona, Texas, etc.)
- Poor thermal management
- Many 2011-2012 cars have <50% SOH by 2024
- Class action lawsuit settled in 2016

### AZE0-0 "Wolf" (Early 2013-2014)
- Better than Canary but still degrades quickly in heat
- Improved motor but same battery thermal issues

### AZE0-1 "Lizard" (Late 2013-2015)
- Heat-resistant chemistry
- Still degrades but slower than Wolf/Canary
- Best of the 24kWh variants

### AZE0-2 (2016-2017)
- Better chemistry (NMC) and capacity
- Occasional BMS firmware issues
- Generally reliable

### ZE1 (2018+)
- **Gateway blocking** makes DIY monitoring difficult
- Otherwise very reliable
- Excellent battery longevity

---

## References

- [dalathegreat/leaf_can_bus_messages](https://github.com/dalathegreat/leaf_can_bus_messages) - DBC files
- [Open Vehicles OVMS](https://docs.openvehicles.com/en/latest/components/vehicle_nissanleaf/docs/index.html) - ZE1 gateway workaround
- [My Nissan Leaf Forum](https://mynissanleaf.com/) - Community knowledge base
- [LeafSpy Documentation](https://leafspy.com/) - Mobile app using these protocols

---

## For OpenLeaf Implementation

**Use these YAML files:**

| Your Leaf | YAML File to Use | DBC Reference |
|-----------|------------------|---------------|
| 2010-2012 | `leaf_ze0.yaml` | LEAF_2011-2017_ZE0_AZEO.dbc |
| 2013-2015 (24kWh) | `leaf_aze0.yaml` | LEAF_2011-2017_ZE0_AZEO.dbc |
| 2016-2017 (30kWh) | `leaf_aze0.yaml` | LEAF_2011-2017_ZE0_AZEO.dbc |
| 2018+ (40/62kWh) | `leaf_ze1.yaml` | LEAF_2018-_ZE1.dbc |

**Note**: AZE0-0, AZE0-1, and AZE0-2 all use the same CAN messages, just with different capacity values.
