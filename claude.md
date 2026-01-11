# OpenLeaf Project Context

**Last Updated:** 2026-01-10

## Current Status

We just completed a major expansion of the state management and testing infrastructure. The project is now ready for **real car testing** with your 2013 Leaf.

### What Just Changed

1. **Expanded LeafState** from 7 fields to **35+ fields** to match all YAML signal definitions
2. **Enhanced test script** to validate which fields populate and save results to JSON
3. **Created comprehensive documentation**:
   - [REQUIREMENTS.md](docs/REQUIREMENTS.md) - Full feature spec (LeafSpy equivalent)
   - [IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) - Audit + checklist
   - [QUICKSTART.md](QUICKSTART.md) - Setup guide

### Ready to Test

All code is staged and ready to commit/push. Once you pull it on your MacBook, you can:

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install pyyaml bleak pyserial

# Configure your BLE adapter address in configs/leaf_2013_24kwh.yaml
# Then run:
python3 test_connection.py
```

The test will:
- ✅ Connect via BLE to your OBD-II adapter
- ✅ Query all 5 PIDs (Groups 0x01-0x04, 0x06)
- ✅ Show which fields get data (✅) vs empty (⚪)
- ✅ Save `test_results.json` with full report
- ✅ Print success rate summary

## Project Architecture

### Transport Layer
- **[openleaf/transports/obd2_unified.py](openleaf/transports/obd2_unified.py)** - Main transport with BLE/Serial support
- **[openleaf/transports/elm327.py](openleaf/transports/elm327.py)** - ELM327 protocol handler
- **[openleaf/transports/connections/](openleaf/transports/connections/)** - BLE/Serial connection implementations

### State Management
- **[openleaf/state.py](openleaf/state.py)** - LeafState dataclass (35+ fields) + StateStore (thread-safe)

### YAML Definitions (3 Generations)
- **[pids/leaf_aze0.yaml](pids/leaf_aze0.yaml)** - 2013-2017 (24/30kWh) - **YOUR CAR**
- **[pids/leaf_ze0.yaml](pids/leaf_ze0.yaml)** - 2011-2012 (24kWh)
- **[pids/leaf_ze1.yaml](pids/leaf_ze1.yaml)** - 2018+ (40/62kWh)

Each YAML has:
- `metadata` (generation, years, battery specs)
- `broadcast_frames` (passive CAN monitoring - not yet integrated)
- `query_pids` (active UDS Service 0x21 queries - **working now**)

### API Layer
- **[openleaf/server.py](openleaf/server.py)** - FastAPI server (port 8000)
- Endpoints: `/health`, `/state`, `/command/clear_dtcs`

### UI Layer
- **[openleaf/ui/kivy/](openleaf/ui/kivy/)** - Kivy touchscreen app
- Basic dashboard exists, needs expansion

## Your 2013 Leaf Data

From the CAN capture analysis ([docs/ref/can_analysis_2013_leaf.md](docs/ref/can_analysis_2013_leaf.md)):

- **Battery Health:** 44% SOH
- **Remaining Capacity:** 126 GIDs = 10.08 kWh
- **Generation:** AZE0 (2013-2017)
- **Battery:** 24kWh AESC LMO

## What's Working

✅ BLE/Serial connections implemented
✅ ELM327 protocol with ISO-TP multi-frame support
✅ Active PID queries (Service 0x21)
✅ YAML loader supports both formats (start_bit + byte_offset)
✅ State management with 35+ fields
✅ Test script with validation tracking

## What's Missing

❌ Not tested with real car yet (**MAIN BLOCKER**)
❌ Passive monitoring not integrated (active queries only)
❌ UI needs cells/health/DTC screens
❌ Power limits (0x1DC) not in YAML yet

## Next Steps

1. **Push this code** (need to configure git first)
2. **Pull on MacBook**
3. **Test with 2013 Leaf** using test_connection.py
4. **Review test_results.json** to see what works
5. **Update UI** based on working signals

## Git Setup Needed

Before you can push, configure git identity:

```bash
git config user.email "your-email@example.com"
git config user.name "Your Name"
```

For SSH (recommended):
```bash
# Generate key if needed
ssh-keygen -t ed25519 -C "your-email@example.com"

# Add to GitHub: https://github.com/settings/keys
cat ~/.ssh/id_ed25519.pub

# Change remote to SSH
git remote set-url origin git@github.com:USERNAME/openleaf.git
```

## Key Files to Review on MacBook

1. **[IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)** - See what's done vs missing
2. **[REQUIREMENTS.md](docs/REQUIREMENTS.md)** - Full feature spec
3. **[pids/leaf_aze0.yaml](pids/leaf_aze0.yaml)** - All 35+ signals for your car
4. **[test_connection.py](test_connection.py)** - Test script to run first

## Known Issues

1. Cell voltage query is slow (~5 seconds for 96 values)
2. ZE1 cars have gateway blocking (requires car ON mode) - doesn't affect you
3. Charge history queries unknown (need research)
4. No WebSocket support yet (polling only)

## Reference Files Added

- All DBC files in [docs/ref/](docs/ref/)
- Real CAN capture from your 2013 Leaf
- Generation breakdown document
- CAN data analysis

## Questions to Answer via Testing

1. Do all 5 PID groups respond?
2. Does cell voltage query (96 cells) work?
3. Do temperature sensors (4 sensors) all work?
4. What's the actual query latency?
5. Does BLE adapter handle multi-frame responses correctly?

---

**Status:** Ready to push and test on real hardware!
