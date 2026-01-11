# OpenLeaf Quick Start Guide

## First-Time Setup (On Laptop)

```bash
# 1. Clone/pull the repo
cd ~/workspace/HDE/openleaf
git pull

# 2. Install Python dependencies (Ubuntu/Debian)
sudo apt install -y python3.12-venv python3-pip

# 3. Create virtual environment
python3 -m venv venv

# 4. Activate venv
source venv/bin/activate

# 5. Install dependencies
pip install pyyaml bleak kivy

# 6. Test YAML loading
python3 -c "
from openleaf.transports.obd2_unified import OBD2Transport
import logging
logging.basicConfig(level=logging.INFO)

transport = OBD2Transport(
    connection_type='ble',
    ble_address='test',
    pid_path='pids/leaf_aze0.yaml'
)
print(f'✅ Loaded {len(transport.pids)} PIDs')
"
```

If you see `✅ Loaded 5 PIDs`, you're good to go!

---

## Running in the Car

### Setup (one time per session)
```bash
cd ~/workspace/HDE/openleaf
source venv/bin/activate
```

### Test Connection (Without UI)
```bash
# Turn car to ON/ACC position first!
python test_connection.py
```

This will:
- Connect to your BLE OBD adapter
- Query 5 battery PIDs
- Print live data
- Stop after 10 iterations (~30 seconds)

**Expected output:**
```
🟢 CONNECTED
Data received: 15 values
   soc_true: 45.2
   ah_capacity: 10.5
   soh_precise: 44.1
   ...
```

### Run Full Dashboard
```bash
python main.py
```

---

## Troubleshooting

### "Module not found" errors
```bash
# Make sure venv is activated (you should see "(venv)" in prompt)
source venv/bin/activate

# Reinstall dependencies
pip install pyyaml bleak kivy
```

### "BLE connection timeout"
- Make sure BLE adapter is paired with laptop
- Check adapter is powered and in range
- Try: `bluetoothctl devices` to see if adapter is visible

### "NO DATA" from car
- Turn car to ON or ACC position (not just power button)
- Make sure OBD adapter is fully plugged in
- Try unplugging/replugging the adapter

### "UNABLE TO CONNECT"
- Adapter might be dead/low battery
- Try different OBD adapter
- Check if LeafSpy still works with this adapter

---

## Files You Care About

### Configs
- `configs/leaf_2013_24kwh.yaml` - Your 2013 Leaf config
- `configs/leaf_2018_40kwh.yaml` - 2018 Leaf config (if you have one)

### PIDs
- `pids/leaf_aze0.yaml` - 2013-2017 Leaf PIDs (24/30kWh)
- `pids/leaf_ze0.yaml` - 2011-2012 Leaf PIDs
- `pids/leaf_ze1.yaml` - 2018+ Leaf PIDs (40/62kWh)

### Logs
- `logs/` - Debug logs when things go wrong

---

## What Gets Displayed

From the 5 PIDs queried:

**Battery Health:**
- SOC (State of Charge) %
- SOH (State of Health) %
- Remaining capacity (Ah)

**Cell Details:**
- All 96 cell voltages
- Min/Max/Delta voltage
- Which cells are balancing

**Temperatures:**
- 4 pack temperature sensors

**Your 2013 Leaf Status (from CAN scan):**
- 44% SOH
- 126 GIDs (~10 kWh remaining)
- About 50-60 miles range

---

## Next Steps After Testing

If everything works:
1. Take screenshots of the dashboard
2. Use it to show buyers the real battery condition
3. Price accordingly (44% SOH = degraded battery)
4. Sell it!

If it doesn't work:
1. Copy the error messages
2. Check logs in `logs/` directory
3. Debug with me!

---

## Pro Tips

- Always turn car ON/ACC before running
- BLE adapters can be finicky - unplug/replug if issues
- Cell voltage query (Group 0x02) takes ~5 seconds (it's slow)
- Logs go to `logs/` with timestamps
- Press Ctrl+C to stop cleanly

Good luck! 🚗⚡
