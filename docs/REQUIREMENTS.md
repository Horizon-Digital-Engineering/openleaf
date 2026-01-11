# OpenLeaf Requirements - Complete Battery Monitoring

## Project Goal
Create a comprehensive Nissan Leaf battery monitoring dashboard that displays all critical battery health and performance metrics for informed buying/selling decisions.

---

## Core Requirements

### 1. Battery State of Charge (SOC)
**Must Display:**
- Current state of charge (%) - high precision (0.1% resolution)
- Usable SOC vs True SOC distinction
- Visual gauge/indicator
- Historical trend (optional future enhancement)

**Data Sources:**
- Active query: Service 0x21, Group 0x01 (precise SOC)
- Passive frame: 0x1DB or equivalent (dashboard SOC)
- Passive frame: 0x55B (high-resolution SOC on ZE0/AZE0)

---

### 2. Battery State of Health (SOH)
**Must Display:**
- Current state of health (%)
- Original vs current capacity
- GIDs (remaining 80Wh increments)
- Estimated range impact
- Capacity bars (12-bar display equivalent)

**Data Sources:**
- Active query: Service 0x21, Group 0x01 (precise SOH)
- Passive frame: 0x5B3 (SOH calculation via byte shift)
- Passive frame: 0x5BC (GIDs, capacity bars)

**Calculations:**
- Remaining kWh = GIDs × 80 / 1000
- SOH% = (Current Ah / Original Ah) × 100
- Estimated range = GIDs × 4 miles/GID (approximate)

---

### 3. Individual Cell Voltages
**Must Display:**
- All 96 cell pair voltages (2S configuration = 96 pairs)
- Min cell voltage
- Max cell voltage
- Delta (max - min) voltage spread
- Visual bar chart showing all cells
- Highlight outliers (cells significantly above/below average)

**Requirements:**
- Update rate: 5-10 seconds (acceptable delay for 96 values)
- Precision: 1 mV resolution
- Color coding:
  - Green: Normal range (3.70V - 4.10V)
  - Yellow: Slightly low/high (3.60V - 3.70V or 4.10V - 4.15V)
  - Red: Concerning (<3.60V or >4.15V)

**Data Source:**
- Active query: Service 0x21, Group 0x02 (all 96 cell voltages)
- Multi-frame ISO-TP response (29 frames total)

**Cell Voltage Analysis:**
- Average cell voltage
- Standard deviation
- Identify weakest cell
- Cell imbalance indicator (delta >50mV = concern)

---

### 4. Battery Pack Voltage & Current
**Must Display:**
- Total pack voltage (V)
- Pack current (A) - signed (negative = charging, positive = discharging)
- Instantaneous power (kW) = Voltage × Current / 1000
- Direction indicator (charging/discharging/idle)

**Update Rate:** Real-time (100ms / 10 Hz)

**Data Sources:**
- Passive frame: 0x1DB (voltage, current, usable SOC)
- Active query: Service 0x21, Group 0x01 (backup)

**Display:**
- Voltage: 0-450V range
- Current: -400A to +200A range (negative = charging)
- Power: -100kW to +100kW

---

### 5. Battery Temperatures
**Must Display:**
- Average pack temperature
- Individual temperature sensors (4 sensors in pack)
- Min/Max temperature across sensors
- Temperature delta (max - min)

**Requirements:**
- Precision: 1°C resolution
- Range: -40°C to +85°C
- Color coding:
  - Blue: <0°C (cold)
  - Green: 0°C - 35°C (optimal)
  - Yellow: 35°C - 45°C (warm)
  - Red: >45°C (hot - degradation risk)

**Data Sources:**
- Passive frame: 0x5BC (average temperature)
- Active query: Service 0x21, Group 0x04 (all 4 sensors)

---

### 6. Cell Balancing Status
**Must Display:**
- Which cells are currently balancing
- Balancing active/inactive indicator
- Visual representation (96-cell bitmap)

**Purpose:**
- Shows BMS actively balancing weak cells
- Indicates pack health (frequent balancing = imbalance issues)

**Data Source:**
- Active query: Service 0x21, Group 0x06 (balancing bitmap)

**Display:**
- 96-cell grid with highlighted cells that are balancing
- Balancing count (how many cells are balancing)

---

### 7. Charge/Discharge Power Limits
**Must Display:**
- Max charge power available (kW)
- Max discharge power available (kW)
- Power limit reason codes (if available)

**Purpose:**
- Understand current battery limitations
- Predict fast-charge capability
- Identify degradation (lower power limits = aging)

**Data Sources:**
- Passive frame: 0x1DC (power limits)
- Active query: Service 0x21, Group 0x01 (backup)

---

### 8. Charge History & Statistics
**Must Display:**
- Quick charge count (L1/L2 charges)
- L3 fast charge count
- Total charge cycles estimate
- Last charge date/time (optional)

**Data Source:**
- Active query: Service 0x21 (specific groups TBD from research)
- May require additional diagnostic commands

---

### 9. Diagnostic Trouble Codes (DTCs)
**Must Display:**
- Active DTCs (P-codes)
- Pending DTCs
- Historical DTC count
- Description of each code

**Functionality:**
- Read DTCs via Service 0x19 (Read DTC)
- Clear DTCs via Service 0x14 (Clear DTC) - with user confirmation
- Monitor MIL (Malfunction Indicator Lamp) status

**Data Source:**
- Standard OBD-II service 0x19

---

### 10. Motor & Inverter Data
**Must Display:**
- Motor temperature (°C)
- Inverter/IGBT temperature (°C)
- Motor RPM (current)
- Motor torque (Nm)
- Input voltage to motor controller

**Purpose:**
- Thermal management monitoring
- Performance verification
- Detect overheating issues

**Data Sources:**
- Passive frame: 0x55A (motor/inverter temps)
- Passive frame: 0x1DA (motor torque, RPM, voltage)

---

### 11. Charging Status (When Plugged In)
**Must Display:**
- Charging status (charging/not charging/complete)
- Charger output power (kW)
- AC input voltage (V)
- J1772 current limit (A)
- Quick charge voltage (V) if DC charging
- Estimated time to full charge

**Data Sources:**
- Passive frame: 0x380 (charger output)
- Passive frame: 0x5BF (J1772/QC status)
- Passive frame: 0x5BC (remaining charge time)

---

### 12. Environmental & Comfort
**Must Display:**
- Outside ambient temperature
- Climate control status
- HVAC power consumption (if active)
- Battery heater status (for cold climates)

**Data Source:**
- Passive frame: 0x54C (climate control, outside temp)
- Passive frame: 0x54F (HVAC power)

---

### 13. Vehicle Identification
**Must Display:**
- Year/Model
- Generation (ZE0, AZE0, ZE1)
- Battery capacity (24kWh, 30kWh, 40kWh, 62kWh)
- VIN (from config or query)
- Odometer reading

**Data Source:**
- Config file (year, model, generation)
- Passive frame: 0x5C5 (odometer)

---

## Data Update Frequencies

### Real-Time (100ms / 10 Hz)
- Pack voltage & current
- Motor torque & RPM
- SOC display
- Temperatures (passive)
- Power limits

### Fast Updates (1-2 seconds)
- Precise SOC/SOH (active query)
- Temperature sensors (active query)
- Cell voltage stats (active query)

### Slow Updates (5-10 seconds)
- Individual cell voltages (96 values = slow)
- Cell balancing status

### Very Slow Updates (10-60 seconds)
- DTCs
- Charge history
- Environmental data

---

## User Interface Requirements

### Dashboard Screen
**Primary View:**
- Large SOC gauge (center, prominent)
- SOH percentage with visual indicator
- Pack voltage & current
- Average temperature
- Instantaneous power (kW)
- Current draw/regen bar

**Layout:**
```
┌─────────────────────────────────────┐
│           SOC: 45.2%                │
│         ╭─────────╮                 │
│         │   45    │  SOH: 44%       │
│         ╰─────────╯                 │
│                                     │
│  Voltage: 360.5V   Temp: 22°C      │
│  Current: -15.2A   Power: -5.5kW   │
│                                     │
│  GIDs: 126  (10.1 kWh remaining)   │
└─────────────────────────────────────┘
```

### Cells Screen
**Cell Voltage View:**
- Bar chart of all 96 cells
- Min/Max/Delta summary at top
- Color-coded bars (green/yellow/red)
- Highlight balancing cells
- Scrollable if needed

**Layout:**
```
┌─────────────────────────────────────┐
│ Cell Voltages                       │
│ Min: 3.82V  Max: 3.89V  Δ: 70mV    │
│                                     │
│ [████] [████] [████] [████] ...     │
│  3.85   3.82   3.87   3.86  ...     │
│                                     │
│ Cell 12 balancing ⚡                │
└─────────────────────────────────────┘
```

### Health Screen
**Battery Health Summary:**
- SOH percentage with trend
- Capacity degradation chart
- Charge cycle counts
- Temperature history (if available)
- Cell imbalance analysis

### DTCs Screen
**Diagnostic Codes:**
- List of active DTCs with descriptions
- Clear codes button
- Warning indicators

### Debug Screen
**Raw Data View:**
- Last 50 CAN messages
- Transport status
- Connection info
- PID query success/fail rates

---

## Technical Requirements

### Data Collection
- **Passive monitoring:** ATMA mode for broadcast frames (future)
- **Active polling:** UDS Service 0x21 diagnostic queries
- **Hybrid approach:** Prioritize passive data, supplement with active queries
- **Error handling:** Graceful degradation if queries fail

### Performance
- **Update rate:** 1 second minimum for dashboard
- **Connection timeout:** 5 seconds before reconnect
- **Query timeout:** 1 second per PID
- **UI responsiveness:** Non-blocking (background thread for data collection)

### Accuracy
- **SOC precision:** ±0.1%
- **Voltage precision:** ±10mV
- **Current precision:** ±0.5A
- **Temperature precision:** ±1°C

### Compatibility
- **ZE0 (2011-2012):** Full support
- **AZE0 (2013-2017):** Full support (24kWh & 30kWh)
- **ZE1 (2018+):** Full support with caveat (requires car ON mode)

---

## Data Storage (Future)

### Recording
- Optional recording to JSON
- Timestamped data points
- Playback capability for analysis

### History (Future Enhancement)
- SQLite database for long-term trends
- SOH degradation over time
- Temperature patterns
- Charge cycle tracking

---

## Priority Levels

### P0 - Critical (Must Have for v1.0)
- SOC, SOH, GIDs
- All 96 cell voltages
- Pack voltage, current, power
- Average temperature
- Connection status

### P1 - High Priority (Should Have)
- Individual temperature sensors (4)
- Cell balancing status
- Power limits
- DTCs
- Motor/inverter temps

### P2 - Medium Priority (Nice to Have)
- Charge history
- Environmental data
- Odometer
- Charge status details

### P3 - Low Priority (Future)
- Historical trends
- Data recording
- Advanced analytics
- Cell degradation predictions

---

## Success Criteria

A successful implementation will:
1. ✅ Display accurate SOC and SOH within ±1%
2. ✅ Show all 96 cell voltages with <10 second refresh
3. ✅ Update dashboard data in real-time (<1 second latency)
4. ✅ Detect and display battery imbalance (delta >50mV)
5. ✅ Work reliably with BLE OBD2 adapter
6. ✅ Provide clear, actionable information for vehicle assessment
7. ✅ Handle connection failures gracefully (reconnect automatically)

---

## Non-Requirements (Out of Scope for v1.0)

- ❌ Remote monitoring (cloud/internet connectivity)
- ❌ Push notifications
- ❌ Multi-vehicle tracking
- ❌ Battery degradation predictions (ML/AI)
- ❌ Navigation integration
- ❌ Vehicle control (charge scheduling, climate, etc.)
- ❌ Social features (sharing data, comparisons)

---

## Reference Data (2013 Leaf Example)

Based on actual captured data:
- SOH: 44%
- GIDs: 126 (10.08 kWh remaining)
- Expected range: ~50-60 miles
- Cell voltage range: 3.70V - 4.10V (typical)
- Pack voltage: 280V - 390V (depending on SOC)
- Max charge power: ~20kW (degraded)
- Max discharge power: ~50kW (degraded)

This represents a **significantly degraded battery** that should be disclosed to buyers.
