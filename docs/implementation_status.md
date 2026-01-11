# OpenLeaf Implementation Status
**Last Updated:** 2026-01-10
**Reference:** [requirements.md](requirements.md)

---

## Overall Status Summary

| Category | Status | Notes |
|----------|--------|-------|
| **Data Collection** | 🟡 Partial | Active queries working, passive monitoring not integrated |
| **State Management** | 🔴 Limited | Only 7 fields in LeafState, needs ~35+ fields |
| **YAML Definitions** | 🟢 Complete | All 3 generations defined with 35+ signals |
| **UI** | 🟡 Basic | Dashboard exists, needs cells/health/DTC screens |
| **Testing** | 🔴 Untested | Not yet tested with real car |

**Legend:**
- 🟢 Complete / Working
- 🟡 Partial / In Progress
- 🔴 Missing / Not Started

---

## Detailed Requirements Audit

### 1. Battery State of Charge (SOC)

#### Current State
**LeafState Fields:**
- ✅ `soc_true: float` - Exists

**YAML Signal Definitions:**
- ✅ `soc_true` - Service 0x21, Group 0x01 (active query)
- ✅ `soc_display` - Passive frame 0x1DB (broadcast)
- ✅ `soc_precise` - Passive frame 0x55B (broadcast, ZE0/AZE0 only)

**Status:** 🟢 **COMPLETE** - Data collection ready
**Missing:**
- ❌ UI gauge for SOC
- ❌ Historical trend tracking

---

### 2. Battery State of Health (SOH)

#### Current State
**LeafState Fields:**
- ✅ `soh: float` - Exists

**YAML Signal Definitions:**
- ✅ `soh_precise` - Service 0x21, Group 0x01 (active query)
- ✅ `soh` - Passive frame 0x5BC (broadcast)
- ✅ `soh_alt` - Passive frame 0x5B3 (broadcast, byte-shift method)
- ✅ `gids` - Passive frame 0x5BC (broadcast)
- ✅ `stored_energy_gids` - Passive frame 0x5B3 (broadcast)
- ✅ `ah_capacity` - Service 0x21, Group 0x01 (active query)
- ✅ `charge_bars` - Passive frame 0x5BC (broadcast)

**Status:** 🟡 **PARTIAL** - Data collection ready, state fields missing
**Missing:**
- ❌ `gids` not in LeafState
- ❌ `ah_capacity` not in LeafState
- ❌ `charge_bars` not in LeafState
- ❌ UI health screen
- ❌ Remaining kWh calculation
- ❌ Estimated range calculation

---

### 3. Individual Cell Voltages

#### Current State
**LeafState Fields:**
- ✅ `cell_voltages: List[float]` - Exists
- ✅ `cell_delta_mv: float` - Exists

**YAML Signal Definitions:**
- ✅ `cell_voltages` - Service 0x21, Group 0x02 (96 cells, active query)
- ✅ `cell_v_min` - Service 0x21, Group 0x03 (active query)
- ✅ `cell_v_max` - Service 0x21, Group 0x03 (active query)
- ✅ `cell_v_delta` - Service 0x21, Group 0x03 (active query)

**Status:** 🟡 **PARTIAL** - Data collection ready, state/UI missing
**Missing:**
- ❌ `cell_v_min` not in LeafState
- ❌ `cell_v_max` not in LeafState
- ❌ UI cells screen with bar chart
- ❌ Color coding (green/yellow/red)
- ❌ Outlier detection
- ❌ Average cell voltage calculation
- ❌ Standard deviation calculation

---

### 4. Battery Pack Voltage & Current

#### Current State
**LeafState Fields:**
- ✅ `pack_voltage: float` - Exists

**YAML Signal Definitions:**
- ✅ `pack_voltage` - Passive frame 0x1DB (broadcast)
- ✅ `pack_current` - Passive frame 0x1DB (broadcast)

**Status:** 🔴 **INCOMPLETE** - Data defined but state missing current/power
**Missing:**
- ❌ `pack_current` not in LeafState
- ❌ `pack_power` not in LeafState (needs calculation)
- ❌ Charging/discharging direction indicator
- ❌ Real-time power display

---

### 5. Battery Temperatures

#### Current State
**LeafState Fields:**
- ✅ `pack_temp_c: float` - Exists (average only)

**YAML Signal Definitions:**
- ✅ `pack_temp_avg` - Passive frame 0x5BC (broadcast)
- ✅ `temp_sensor_1` - Service 0x21, Group 0x04 (active query)
- ✅ `temp_sensor_2` - Service 0x21, Group 0x04 (active query)
- ✅ `temp_sensor_3` - Service 0x21, Group 0x04 (active query)
- ✅ `temp_sensor_4` - Service 0x21, Group 0x04 (active query)

**Status:** 🟡 **PARTIAL** - Average temp only, individual sensors missing
**Missing:**
- ❌ `temp_sensor_1` not in LeafState
- ❌ `temp_sensor_2` not in LeafState
- ❌ `temp_sensor_3` not in LeafState
- ❌ `temp_sensor_4` not in LeafState
- ❌ `temp_min` not in LeafState
- ❌ `temp_max` not in LeafState
- ❌ `temp_delta` not in LeafState
- ❌ UI temperature display with color coding

---

### 6. Cell Balancing Status

#### Current State
**LeafState Fields:**
- ❌ None

**YAML Signal Definitions:**
- ✅ `balancing_bitmap` - Service 0x21, Group 0x06 (active query)

**Status:** 🔴 **MISSING** - Data defined but no state storage
**Missing:**
- ❌ `balancing_bitmap` not in LeafState
- ❌ `balancing_active` not in LeafState
- ❌ `balancing_count` not in LeafState
- ❌ UI balancing visualization
- ❌ Bitmap decoder

---

### 7. Charge/Discharge Power Limits

#### Current State
**LeafState Fields:**
- ❌ None

**YAML Signal Definitions:**
- ❌ NOT DEFINED in current YAML (need to add!)

**Status:** 🔴 **MISSING** - Not defined
**Missing:**
- ❌ Power limits not in YAML (0x1DC broadcast frame)
- ❌ `max_charge_power` not in LeafState
- ❌ `max_discharge_power` not in LeafState
- ❌ Power limit reason codes
- ❌ UI display

---

### 8. Charge History & Statistics

#### Current State
**LeafState Fields:**
- ❌ None

**YAML Signal Definitions:**
- ❌ NOT DEFINED (need research on which Service 0x21 groups)

**Status:** 🔴 **MISSING** - Needs research
**Missing:**
- ❌ Charge cycle count queries
- ❌ L1/L2/L3 charge counts
- ❌ State storage
- ❌ UI display

---

### 9. Diagnostic Trouble Codes (DTCs)

#### Current State
**LeafState Fields:**
- ✅ `dtcs: List[str]` - Exists

**YAML Signal Definitions:**
- ❌ NOT APPLICABLE (standard OBD-II Service 0x19, not in YAML)

**Status:** 🟡 **PARTIAL** - State exists, implementation missing
**Missing:**
- ❌ Service 0x19 query implementation
- ❌ Service 0x14 clear implementation
- ❌ DTC decoder (P-codes to descriptions)
- ❌ UI DTC screen
- ❌ MIL status

---

### 10. Motor & Inverter Data

#### Current State
**LeafState Fields:**
- ❌ None

**YAML Signal Definitions:**
- ✅ `motor_temp` - Passive frame 0x55A (broadcast)
- ✅ `igbt_temp` - Passive frame 0x55A (broadcast)
- ✅ `motor_rpm` - Passive frame 0x1DA (broadcast)
- ✅ `motor_torque` - Passive frame 0x1DA (broadcast)
- ✅ `motor_voltage` - Passive frame 0x1DA (broadcast)

**Status:** 🔴 **MISSING** - Data defined but no state storage
**Missing:**
- ❌ All motor/inverter fields not in LeafState
- ❌ UI display
- ❌ Passive monitoring not integrated

---

### 11. Charging Status

#### Current State
**LeafState Fields:**
- ❌ None

**YAML Signal Definitions:**
- ✅ `charger_power` - Passive frame 0x380 (broadcast)
- ✅ `ac_voltage` - Passive frame 0x380 (broadcast)
- ✅ `j1772_current_limit` - Passive frame 0x5BF (broadcast)
- ✅ `qc_voltage` - Passive frame 0x5BF (broadcast)

**Status:** 🔴 **MISSING** - Data defined but no state storage
**Missing:**
- ❌ All charging fields not in LeafState
- ❌ Charging status enum
- ❌ Time to full calculation
- ❌ UI charging screen
- ❌ Passive monitoring not integrated

---

### 12. Environmental & Comfort

#### Current State
**LeafState Fields:**
- ❌ None

**YAML Signal Definitions:**
- ✅ `outside_temp` - Passive frame 0x54C (broadcast)

**Status:** 🟡 **PARTIAL** - Some data defined
**Missing:**
- ❌ `outside_temp` not in LeafState
- ❌ Climate control status not defined
- ❌ HVAC power not defined
- ❌ Battery heater status not defined

---

### 13. Vehicle Identification

#### Current State
**LeafState Fields:**
- ❌ None

**YAML Signal Definitions:**
- ✅ `range_km` - Passive frame 0x5A9 (broadcast)

**Status:** 🔴 **MISSING** - Mostly from config, odometer not captured
**Missing:**
- ❌ Odometer not defined (0x5C5 frame not in YAML)
- ❌ VIN query not implemented
- ❌ Vehicle info from config not exposed to UI

---

## Infrastructure Status

### Data Collection Layer

| Component | Status | Notes |
|-----------|--------|-------|
| BLE Connection | 🟢 Complete | Bleak-based, tested locally |
| Serial Connection | 🟢 Complete | Restored, pyserial-based |
| ELM327 Protocol | 🟢 Complete | ISO-TP multi-frame support |
| Active PID Queries | 🟢 Complete | Service 0x21 working |
| Passive Monitoring | 🔴 Missing | Capture script exists, not integrated |
| YAML Loading | 🟢 Complete | Supports both `pids` and `query_pids` |

### State Management

| Component | Status | Notes |
|-----------|--------|-------|
| StateStore | 🟢 Complete | Thread-safe RLock wrapper |
| LeafState | 🔴 Incomplete | Only 7 fields, needs 35+ |
| State Updates | 🟢 Complete | Works with any field name |
| Snapshots | 🟢 Complete | Returns dict copy |

### API Layer

| Component | Status | Notes |
|-----------|--------|-------|
| FastAPI Server | 🟢 Complete | Port 8000, CORS enabled |
| /health endpoint | 🟢 Complete | Returns status |
| /state endpoint | 🟢 Complete | Returns full state |
| /command/clear_dtcs | 🟡 Partial | Exists but untested |
| WebSocket | 🔴 Missing | Currently polling only |

### UI Layer

| Component | Status | Notes |
|-----------|--------|-------|
| Kivy App | 🟢 Complete | Screen manager working |
| Dashboard Screen | 🟡 Basic | Gauges work, needs more metrics |
| Cells Screen | 🔴 Missing | Cell graph widget exists but not populated |
| Health Screen | 🔴 Missing | Not implemented |
| DTCs Screen | 🔴 Missing | Not implemented |
| Debug Screen | 🟡 Partial | Shows transport log |
| API Polling | 🟢 Complete | 500ms updates |

---

## Priority Checklist

### P0 - Critical (Must Have for v1.0)

#### Data Collection
- [x] Load PIDs from YAML
- [x] Query Service 0x21 Group 0x01 (SOC, SOH, capacity)
- [x] Query Service 0x21 Group 0x02 (96 cell voltages)
- [x] Query Service 0x21 Group 0x03 (cell stats)
- [x] Query Service 0x21 Group 0x04 (temperature sensors)
- [ ] **Add `max_charge_power` and `max_discharge_power` to YAML (0x1DC)**
- [ ] **Integrate passive monitoring for real-time voltage/current**

#### State Management
- [ ] **Expand LeafState with all 35+ fields**
  - [ ] Add `pack_current`
  - [ ] Add `pack_power` (calculated)
  - [ ] Add `gids`
  - [ ] Add `ah_capacity`
  - [ ] Add `charge_bars`
  - [ ] Add `cell_v_min`, `cell_v_max`
  - [ ] Add `temp_sensor_1` through `temp_sensor_4`
  - [ ] Add `temp_min`, `temp_max`, `temp_delta`
  - [ ] Add `balancing_bitmap`, `balancing_count`
  - [ ] Add `motor_temp`, `igbt_temp`, `motor_rpm`, `motor_torque`
  - [ ] Add `charger_power`, `ac_voltage`, `charging_status`
  - [ ] Add `outside_temp`, `range_km`
  - [ ] Add `max_charge_power`, `max_discharge_power`

#### UI
- [ ] **Update Dashboard Screen**
  - [ ] Add pack current display
  - [ ] Add instantaneous power (kW)
  - [ ] Add GIDs display
  - [ ] Add remaining kWh calculation
  - [ ] Add charging/discharging indicator
- [ ] **Create Cells Screen**
  - [ ] 96-cell bar chart
  - [ ] Min/Max/Delta summary
  - [ ] Color coding (green/yellow/red)
  - [ ] Highlight balancing cells
- [ ] **Test with real car** ⚠️ **CRITICAL**

### P1 - High Priority (Should Have)

- [ ] Add Service 0x21 Group 0x06 (balancing) to LeafState
- [ ] Implement Service 0x19 (read DTCs)
- [ ] Implement Service 0x14 (clear DTCs)
- [ ] Create DTCs Screen in UI
- [ ] Create Health Screen in UI
- [ ] Add motor/inverter temps to dashboard
- [ ] Add power limits display
- [ ] Handle connection failures gracefully

### P2 - Medium Priority (Nice to Have)

- [ ] Add odometer (0x5C5) to YAML
- [ ] Integrate passive monitoring for broadcast frames
- [ ] Add charge history queries (research needed)
- [ ] Add environmental data display
- [ ] Recording to JSON
- [ ] Playback mode for debugging

### P3 - Low Priority (Future)

- [ ] Historical trends (SQLite)
- [ ] Cell degradation analysis
- [ ] WebSocket for push updates
- [ ] Multi-vehicle profiles
- [ ] Export reports (PDF/CSV)

---

## Testing Checklist

### Local Testing (Synthetic Data)
- [ ] Update synthetic.py with realistic 2013 Leaf data
- [ ] Test all screens with synthetic transport
- [ ] Verify UI updates correctly
- [ ] Test state store thread safety

### Hardware Testing (Real Car)
- [ ] Test BLE connection to adapter
- [ ] Test active PID queries (Group 0x01-0x06)
- [ ] Verify cell voltage query (96 values)
- [ ] Verify temperature sensor query (4 sensors)
- [ ] Test reconnection after adapter disconnect
- [ ] Test with car OFF vs ON
- [ ] Measure query latency

### Integration Testing
- [ ] Test API endpoints
- [ ] Test UI polling loop
- [ ] Test DTC read/clear
- [ ] Test error handling (bad responses)
- [ ] Test timeout handling

---

## Known Issues & Blockers

### Blockers
1. ⚠️ **Not tested with real car yet** - Main blocker
2. ⚠️ **LeafState too limited** - Only 7 fields vs 35+ needed
3. ⚠️ **Passive monitoring not integrated** - Relying on active queries only

### Known Issues
1. Cell voltage query is slow (~5 seconds for 96 values)
2. Power limits (0x1DC) not defined in YAML
3. Charge history queries unknown (need research)
4. ZE1 gateway blocking (requires car ON mode)

### Technical Debt
1. No WebSocket support (polling only)
2. No historical data storage
3. No unit tests
4. No CI/CD
5. Hardcoded cell count (96)
6. No error recovery for partial data

---

## Next Immediate Steps

1. **Expand LeafState** - Add all 35+ fields (30 minutes)
2. **Test with real 2013 Leaf** - Verify data collection works (1 hour)
3. **Update Dashboard UI** - Show pack current, power, GIDs (1 hour)
4. **Create Cells Screen** - 96-cell bar chart (2 hours)
5. **Add power limits to YAML** - 0x1DC frame (30 minutes)
6. **Update synthetic transport** - Realistic test data (1 hour)

**Estimated time to P0 complete:** 6-8 hours of focused work

---

## Success Metrics

✅ **v1.0 Success Criteria:**
- [ ] Displays accurate SOC, SOH, GIDs
- [ ] Shows all 96 cell voltages with color coding
- [ ] Real-time pack voltage, current, power
- [ ] 4 individual temperature sensors
- [ ] Cell balancing visualization
- [ ] Detects imbalance (delta >50mV)
- [ ] Works reliably with BLE adapter
- [ ] Reconnects automatically on disconnect
- [ ] Updates dashboard <1 second latency
- [ ] Tested with actual 2013 Leaf

**Current Progress:** ~40% complete
