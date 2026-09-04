# BatteryLogger — Project Reference

## What this is

Real-time logger and offline analyzer for CEGASA BCS battery systems (E_BICK_LV_280, 280 Ah nominal).

Two independent tools:
- **`main_logger.py`** — polls BMS REST API, writes timestamped CSV rows
- **`visual_log.py`** — Dash web app, loads CSV, shows charts + cycle table

## Run

```bash
# First time: ./run.sh   (creates env, installs deps)

source env/bin/activate

# Logger (connects to BMS at IP in cfg.ini)
python src/main_logger.py

# Analyzer (drag-and-drop CSV at http://localhost:8050)
python src/visual_log.py
```

## Key files

| File | Role |
|------|------|
| `src/main_logger.py` | Entry point, CLI args, shutdown handling |
| `src/api_controller.py` | Async aiohttp client; polls `/api/bcs/home`, `/info`, `/config` |
| `src/csv_writer.py` | Appends rows to CSV; daily rotation optional |
| `src/datastruct.py` | `BatteryData` (thread-safe, async); `BatteryInfo` dataclass tree |
| `src/visual_log.py` | Dash app: upload → parse → stats + cycle table + 6 charts |
| `cfg.ini` | IP, poll rates, cell count, alert thresholds (repo root — resolved relative to cwd) |
| `run.sh` | Creates `env/`, installs `requirements.txt` |
| `doc/` | Additional documentation |

## BMS API endpoints

| Endpoint | Used for |
|----------|----------|
| `/api/bcs/home` | Live data (voltage, current, SOC, cells, temps, capacity counters) |
| `/api/bcs/info` | Firmware versions, serial numbers |
| `/api/bcs/config` | Battery model, topology, nominal capacity |

## CSV columns to know

All `BatteryInfo` fields are flattened with `_` separator:

| Column | Meaning |
|--------|---------|
| `capacity_capacityChCurrentCycle` | Ah charged in ongoing charge cycle (resets to 0 when discharge starts) |
| `capacity_capacityDchCurrentCycle` | Ah discharged in ongoing discharge cycle (resets to 0 when charge starts) |
| `capacity_capacityChLastCycle` | Ah from last completed charge cycle |
| `capacity_capacityDchLastCycle` | Ah from last completed discharge cycle |
| `capacity_usefulCapacity` | BMS-reported usable capacity (≈ 266 Ah for 280 Ah cell) |
| `meta_capacity_ah` | Nominal capacity from config (280 Ah, constant) |
| `vcell_corrected_vcell` | IR-compensated cell voltage (derived in `datastruct.py`) |

## Cycle analysis (visual_log.py)

`detect_cycles(df)` segments the log into charge/discharge half-cycles by watching for resets in the BMS Ah counters. Validates each segment against mean current direction to handle BMS mid-cycle counter resets (observed behavior: BMS resets `capacityChCurrentCycle` without starting a discharge).

`build_cycle_table(cycles)` renders a Bootstrap card with:
- Type badge (↓ Discharge red / ↑ Charge green)
- Period, duration, SOC start→end, ΔSOC
- Ah (BMS) vs Theo. Ah (`usefulCapacity × ΔSOC / 100`)
- Match % (green ≥95%, amber ≥85%, red <85%); suppressed for partial segments
- Partial flag for segments cut by log boundaries

**Observed results on E_BICK_LV_280:**

| Cycle | Type | SOC | Ah | Match |
|-------|------|-----|----|-------|
| Full discharge | 100% → 20% | ~80% | 212 Ah | ~100% |
| Full charge | 20% → 100% | ~80% | 210 Ah | ~99% |

Useful capacity (266 Ah) × 80% ΔSOC = 212.8 Ah — matches BMS counter exactly. Nominal 280 Ah is never fully used (14 Ah reserve held by BMS).

## Config reference (cfg.ini)

```ini
[Battery_API]
IP=192.168.55.193
PollInterval=5          ; seconds between live polls

[Logging]
LogFrequency=5          ; seconds between CSV rows
RotateDaily=false       ; true = new file at midnight

[Battery_Config]
NumCells=15             ; cells in series per module
NumModules=1            ; modules per string

[Alerts]
SocLowThreshold=20
TempHighThreshold=40
```

## Dependencies

```
aiohttp, dash, dash-bootstrap-components, pandas, plotly
```

Python ≥ 3.10 required (uses `X | Y` union type hints).
