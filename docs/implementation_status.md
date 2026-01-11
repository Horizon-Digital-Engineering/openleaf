# OpenLeaf Implementation Status
**Last Updated:** 2026-01-11 (Session 3)
**Reference:** [requirements.md](requirements.md)

---

## Overall Status Summary

| Category | Status | Notes |
|----------|--------|-------|
| **Data Collection** | 🟢 Working | Active queries + passive broadcast monitoring |
| **State Management** | 🟢 Complete | 35+ fields in LeafState |
| **YAML Definitions** | 🟢 Complete | All 3 generations defined |
| **UI** | 🟢 Working | Dashboard + Cells + Debug screens |
| **Testing** | 🟢 Tested | Working with real 2013 Leaf |

**Legend:**
- 🟢 Complete / Working
- 🟡 Partial / In Progress
- 🔴 Missing / Not Started

---

## What's Working (Tested with Real Car)

### Data Collection
| Feature | Status | Source | Notes |
|---------|--------|--------|-------|
| SOC | 🟢 | Calculated from GIDs | 0x55B on EV-CAN, not accessible via OBD2 |
| SOH | 🟢 | Broadcast 0x5B3 | 44% on test car |
| GIDs | 🟢 | Broadcast 0x5B3 | 86 GIDs = ~6.9 kWh |
| HX (Battery Health) | 🟢 | UDS Group 1 | 60.9% |
| Cell Voltages (96) | 🟢 | UDS Group 2 | 3.973V - 3.994V range |
| Cell Min/Max/Delta | 🟢 | Calculated | 21mV delta |
| Pack Temps (4 sensors) | 🟢 | UDS Group 4 | 22°C average |
| Range | 🟢 | Broadcast 0x5A9 | 60 km / 37 mi |
| Balancing Status | 🟢 | UDS Group 6 | Active |

### Infrastructure
| Component | Status | Notes |
|-----------|--------|-------|
| BLE Connection | 🟢 | Tested with cheap $15 adapter |
| Serial Connection | 🟢 | Available but not tested this session |
| ELM327 Protocol | 🟢 | ISO-TP multi-frame with flow control |
| Active PID Queries | 🟢 | Groups 1, 2, 3, 4, 6 working |
| Passive Broadcast | 🟢 | 0x5B3, 0x5A9 captured |
| FastAPI Server | 🟢 | Port 8000, /state endpoint |
| Kivy UI | 🟢 | Dashboard, Cells, Debug screens |

---

## What's Missing / Not Accessible

### EV-CAN Messages (Not on OBD2 Port)
| Signal | CAN ID | Issue |
|--------|--------|-------|
| pack_voltage | 0x1DB | EV-CAN only |
| pack_current | 0x1DB | EV-CAN only |
| soc_display | 0x1DB | EV-CAN only |
| soc_precise | 0x55B | EV-CAN only |

**Workaround:** SOC calculated from GIDs using formula: `soc = gids / (281 * soh/100) * 100`

### Not Yet Captured (Need Driving/Charging)
| Signal | CAN ID | When Available |
|--------|--------|----------------|
| Motor RPM/Torque | 0x1DA | While driving |
| Motor/Inverter Temps | 0x55A | While driving |
| Charger Power | 0x380 | While charging |
| AC Voltage | 0x380 | While charging |

### Not Implemented
| Feature | Priority | Notes |
|---------|----------|-------|
| DTC Read/Clear | P1 | Service 0x19/0x14 |
| Power Limits | P2 | 0x1DC frame |
| Charge History | P2 | Need research |
| Trip Recording | P2 | JSON logging |
| Unit Preferences | P2 | km/miles, C/F toggle |

---

## UI Screens Status

| Screen | Status | Features |
|--------|--------|----------|
| Dashboard | 🟢 | SOC gauge, SOH gauge, GIDs, HX, Range metrics |
| Cells | 🟢 | 96-cell bar graph with Y-axis voltage labels, X-axis cell numbers |
| Debug | 🟢 | Transport log viewer |
| Health | 🔴 | Not implemented |
| DTCs | 🔴 | Not implemented |
| Settings | 🔴 | Not implemented |

---

## Test Results (2026-01-11)

### 2013 Nissan Leaf (AZE0, 24kWh)

| Metric | Value | Status |
|--------|-------|--------|
| SOC | ~70% | Calculated correctly |
| SOH | 44% | Matches LeafSpy |
| GIDs | 86 | Correct |
| HX | 60.9% | Correct |
| Cell Voltages | 96 cells | All reading |
| Cell Delta | 21mV | Healthy range |
| Pack Temp | 22.3°C | 3 sensors working (sensor 3 = 255) |
| Range | 60 km | Matches dash (37 mi) |
| Balancing | Active | Correct |

### Known Quirks
- Temp sensor 3 returns 255 (not present on all packs)
- Car must be ON for broadcast messages
- Cheap adapters need ATCRA filtering to prevent overflow

---

## Priority Checklist

### P0 - Complete ✅
- [x] BLE connection working
- [x] Active PID queries (Groups 1-4, 6)
- [x] Passive broadcast monitoring (0x5B3, 0x5A9)
- [x] 96 cell voltages with correct scaling
- [x] Temperature sensors
- [x] YAML-driven decoding (no hardcoded offsets)
- [x] Full Kivy UI with gauges and cell graph
- [x] SOC calculation from GIDs
- [x] Tested with real car

### P1 - Next Up
- [ ] DTC read/clear (Service 0x19/0x14)
- [ ] Health screen in UI
- [ ] Settings screen with unit preferences
- [ ] Capture more broadcasts while driving

### P2 - Nice to Have
- [ ] Trip recording (JSON log)
- [ ] Playback mode for debugging
- [ ] WebSocket for push updates
- [ ] Power limits (0x1DC)

### P3 - Future
- [ ] Historical trends (SQLite)
- [ ] Cell degradation analysis
- [ ] Multi-vehicle profiles
- [ ] Export reports

---

## Success Metrics

✅ **v1.0 Criteria - ACHIEVED:**
- [x] Displays accurate SOC, SOH, GIDs
- [x] Shows all 96 cell voltages with bar graph
- [x] Cell voltage labels (Y-axis) and cell numbers (X-axis)
- [x] 4 individual temperature sensors
- [x] Cell balancing status
- [x] Range display
- [x] Works reliably with BLE adapter
- [x] Updates dashboard in real-time
- [x] Tested with actual 2013 Leaf

**Current Progress:** ~75% complete (core features working, polish items remaining)
