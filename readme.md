# OpenLeaf

OpenLeaf is a hardware-agnostic telemetry engine for the Nissan Leaf. It ingests vehicle data
from different transports (synthetic, OBD2, CAN, playback) and exposes a unified state via a
simple HTTP API so any UI can render or act upon it.

## Getting Started (Synthetic Mode)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .[dev]
python main.py
```

### Quick start via helper scripts

For quick local testing you can use the provided scripts (they create `.venv`, install dependencies, and background the processes):

```bash
bash start.sh server   # default: starts just the FastAPI server (log: openleaf_server.log)
bash start.sh ui       # launches the Kivy UI (log: openleaf_ui.log)
bash start.sh all      # spins up both

bash stop.sh server    # stop server
bash stop.sh ui        # stop UI
bash stop.sh all       # stop both
```

Then query the API:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/state
```

## Touchscreen UI (Kivy)

An early touchscreen dashboard lives under `openleaf/ui/kivy`. It polls the same backend API, so
start the FastAPI server (synthetic mode is fine) and in a separate shell run:

```bash
pip install -e .[ui]
python openleaf/ui/kivy/main.py
```

The UI targets 1024x600 touch displays and shows SOC/SOH gauges plus pack metrics, updating every
0.5s. A second screen (use the arrow buttons along the bottom) renders a LeafSpy-style cell graph
using the configured `cell_count`, and a third screen provides a DTC viewer with placeholder “pull”
and “clear” actions. Clear commands already hit the FastAPI endpoint; full DTC retrieval will land
once we implement it in the backend. A fourth “Debug” screen lists recent OBD transport TX/RX lines
so you can verify ELM327 chatter from the UI.

## Configuration

Runtime configuration lives in `config.yaml`. The default ships with the synthetic transport
so you can get immediate feedback without hardware.

```yaml
transport:
  type: "synthetic"
  update_interval_sec: 0.5

logging:
  enabled: false
  path: "./leaf.log"

vehicle:
  year: 2013
  generation: "ZE0"
  model: "SV"
  pack_kwh: 24.0
  cell_count: 96
  # 2011-2015 ZE0 24 kWh -> 96 cells
  # 2016-2017 ZE0 30 kWh -> 96 cells
  # 2018-2021 ZE1 40 kWh -> 96 cells
  # 2019-2024 ZE1 e+ 62 kWh -> 96 cells
```

The `vehicle` block lets you describe the battery pack you’re targeting. `cell_count` feeds the
synthetic transport (and future UIs) so graphs like the per-cell view know how many modules to
render. Later transports (OBD, CAN, playback) will honor these settings to parse the correct
signals for each Leaf generation.

Preset configs live in `configs/`:

- `configs/synthetic.yaml` — default synthetic mode.
- `configs/leaf_2013_24kwh.yaml` — OBD for a 2013 ZE0 (24 kWh, 96 cells).
- `configs/leaf_2018_40kwh.yaml` — OBD for a 2018 ZE1 (40 kWh, 96 cells).

Point the server at any config via CLI or env:

```bash
python main.py configs/leaf_2013_24kwh.yaml
bash start.sh server configs/leaf_2013_24kwh.yaml
OPENLEAF_CONFIG=configs/leaf_2018_40kwh.yaml python main.py
```

## Logging / Debug

Set `logging.enabled: true` in your config (defaults to `./logs`) to emit:

- `logs/server.log` for app/server events
- `logs/connection.log` for all transport TX/RX plus per-adapter files (`logs/connection_<adapter>.log`)
- `logs/ui.log` (stdout/err) and `logs/kivy_ui_*.txt` when using the helper scripts (UI logging)

Adjust `logging.level` for verbosity (e.g., `DEBUG` for maximum detail).

## Bluetooth OBD/ELM327 Mode

1. Pair your ELM327 adapter over Bluetooth on the target device (e.g., Raspberry Pi) and note
   the rfcomm device path (commonly `/dev/rfcomm0`).
2. Update `config.yaml`:

```yaml
transport:
  type: "obd"
  serial_port: "/dev/rfcomm0"
  baudrate: 115200
  timeout_sec: 1.0
  pid_path: "pids/leaf.yaml"
  update_interval_sec: 0.5
```

3. Start the server (`python main.py`). The OBD transport will:
   - Open the serial port and run an ELM327 handshake (`ATZ`, `ATI`, `ATL1`, `ATH1`, `ATS1`,
     `ATAL`, `ATSP6`).
   - For each PID defined in `pids/leaf.yaml`, set the CAN header (`ATSH`), send the request
     (for example `02 21 01`), assemble multi-frame ISO-TP replies, and decode signals into the
     shared state store.
   - If the adapter or vehicle drops, the loop will close the port, sleep briefly, and re-run
     the initialization sequence on reconnect.

PID definitions live in `pids/leaf.yaml` so you can tweak or add signals without code changes.
Each entry declares the request/response IDs, service/data identifier, and per-signal bit
positions plus scaling/offset. The defaults mirror LeafSpy-style requests to the BMS (`21 01`
for pack metrics and `21 61` for SOH).

## Architecture

```
Transports (synthetic/OBD/CAN/playback) --> StateStore --> FastAPI HTTP API --> UI clients
```

Transports feed decoded Leaf signals into a shared `StateStore`. The FastAPI server exposes
`/state`, `/health`, and command endpoints for control flows. Different UIs (web, Kivy, etc.)
can poll or subscribe to the state endpoints. Logging and playback transports will make it
possible to capture and replay real drives.

## Roadmap

1. Synthetic transport and HTTP API (this phase)
2. OBD/Bluetooth ELM327 transport
3. CAN/SocketCAN transport
4. Playback/logging engine
5. Touch-friendly UI built on top of the state API

## License

OpenLeaf is distributed under the terms of the GNU General Public License v3.0 or
later. See `LICENSE` for details.
