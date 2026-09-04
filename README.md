# Battery Logger v2.0

Real-time logging and offline analysis tool for CEGASA BCS battery systems.

## Requirements

- Python **3.10+**
- Dependencies listed in `requirements.txt`

## Installation

```bash
# One-shot: creates ./env and installs dependencies
./run.sh

# Or manually
python -m venv env
source env/bin/activate        # Linux / Mac
env\Scripts\activate           # Windows
pip install -r requirements.txt
```

## Configuration (`cfg.ini`)

Edit before first run:

```ini
[Battery_API]
IP=192.168.55.193       ; IP address of the BMS
PollInterval=2          ; Live data poll rate (seconds)

[Logging]
LogFrequency=15         ; How often to write a CSV row (seconds)
RotateDaily=true        ; Start a new CSV file each midnight

[Battery_Config]
NumCells=15             ; Cells in series per module (used for IR and corrected VCell calc)
NumModules=1            ; Modules per string

[Alerts]
SocLowThreshold=20      ; Warn when SOC drops below this %
TempHighThreshold=40    ; Warn when max cell temperature exceeds this °C
```

## Usage

### Logger (`src/main_logger.py`)

```bash
python src/main_logger.py
```

On startup, the logger:
1. Fetches firmware versions from `/api/bcs/info` (MCS and SCS)
2. Fetches battery config from `/api/bcs/config` (model, topology, capacity)
3. Prints device info to the console
4. Starts polling `/api/bcs/home` and writing timestamped CSV rows

All device metadata (firmware versions, serial numbers, battery model) is embedded in every CSV row so each file is self-contained.

**CLI options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | `cfg.ini` | Path to config file |
| `--log-level LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `--no-csv` | off | Monitor only — no CSV written |
| `--dry-run` | off | Test connectivity, print one snapshot, exit |
| `--poll-interval SECS` | from config | Override API poll rate |
| `--log-freq SECS` | from config | Override CSV row frequency |
| `--status-interval SECS` | `10` | Console status print rate |
| `--version` | — | Print version and exit |

```bash
# Test connectivity before committing to a log session
python src/main_logger.py --dry-run

# Verbose output — shows every API call
python src/main_logger.py --log-level DEBUG

# Monitor only, no file written
python src/main_logger.py --no-csv

# Custom config path
python src/main_logger.py --config /data/site_a/cfg.ini
```

### Log Analyzer (`src/visual_log.py`)

```bash
python src/visual_log.py
```

Open [http://localhost:8050](http://localhost:8050), then drag and drop a CSV from the `csv/` folder.

**Device info panel** (top of page) shows, parsed from the CSV metadata:

| Field | Source |
|-------|--------|
| Battery model | `/api/bcs/config` |
| MCS firmware version + serial | `/api/bcs/info` → `MCS` |
| SCS firmware version + serial | `/api/bcs/info` → `SCS_01` |
| Topology (strings × modules) | `/api/bcs/config` |
| Nominal capacity (Ah) | `/api/bcs/config` |
| Inverter model | `/api/bcs/config` |

**Session stats bar** (below device info) shows: duration, record count, SOC range, max temperature, peak charge and discharge current.

**Charts:**

| Chart | Signals |
|-------|---------|
| Power | Charge (green fill) / Discharge (red fill) |
| Voltage | Total pack voltage, SOP charge/discharge limits |
| Current | Pack current, SOP charge/discharge limits |
| SOC & SOH | State of charge (filled), state of health (dashed) |
| Cell Voltages | Max, Min, Avg, Corrected (IR-compensated) |
| Temperatures | Max, Min, Ambient, PCB |
| Internal Resistance | Pack total, per-cell |

All charts share a **synchronized zoom axis** — drag to zoom on any chart and all others follow. Double-click to reset.

A **Export HTML Report** button generates a standalone `.html` file with all charts embedded.

## CSV Format

Files are saved in `csv/` with the pattern:
```
battery_log_E_BICK_LV_280_20260512_143200.csv
```

Each row contains:

| Columns | Description |
|---------|-------------|
| `Timestamp` | Row write time (`YYYY-MM-DD HH:MM:SS`) |
| `meta_mcs_fw` | MCS core firmware version (e.g. `v1.16.10`) |
| `meta_scs_fw` | SCS core firmware version |
| `meta_mcs_serial` | MCS full serial number |
| `meta_scs_serial` | SCS full serial number |
| `meta_battery_model` | Battery model string (e.g. `E_BICK_LV_280`) |
| `meta_strings` | Number of strings |
| `meta_modules_per_string` | Modules per string |
| `meta_capacity_ah` | Nominal capacity (Ah) |
| `meta_inverter` | Converter model |
| Live fields… | All `BatteryInfo` fields (voltage, current, SOC, cell voltages, temps, capacity, aging, …) |

## Remote Access

Both tools bind to `0.0.0.0` and are reachable from other machines on the same network.

Find the IP of the logging machine (e.g. `192.168.55.10`) and open:
- Analyzer: `http://192.168.55.10:8050`

Windows users may need to allow the port through the firewall.

## File Structure

```
BatteryLogger/
├── src/
│   ├── main_logger.py     Entry point — logger + monitor
│   ├── visual_log.py      Offline CSV analyzer (Dash)
│   ├── api_controller.py  Async API client (home / info / config endpoints)
│   ├── csv_writer.py      CSV logging with device metadata and daily rotation
│   └── datastruct.py      Data structures and derived calculations
├── doc/                   Additional documentation
├── cfg.ini                Configuration
├── requirements.txt       Python dependencies
├── run.sh                 Creates venv + installs dependencies
└── csv/                   Log files (auto-created on first run)
```
