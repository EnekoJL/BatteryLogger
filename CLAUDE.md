# BatteryLogger — Project Reference

## What this is

Real-time logger and offline analyzer for CEGASA BCS battery systems (E_BICK_LV_280, 280 Ah nominal).

Two independent tools sharing one domain layer:
- **logger** (`entrypoints/logger_main.py`) — polls BMS REST API, writes timestamped CSV rows
- **analyzer** (`entrypoints/analyzer_main.py`) — Dash web app, loads CSV, shows charts + cycle table

Package: `src/batterylogger/`, built as hexagonal architecture (ports & adapters) + SOLID.
`domain/` and `application/` never import aiohttp/Dash/csv/configparser — only
`domain/ports.py` interfaces. Concrete adapters implement those ports;
`bootstrap/container.py` is the only place a concrete adapter gets wired to a
use-case. See `doc/architecture.md` for the full breakdown and rationale.

**Note:** a pre-refactor flat-file version (the same code as plain
`main_logger.py`/`visual_log.py`/etc. at repo root) is preserved at
`../BatteryLogger_v1_flat` and on git branch history — not something to sync
with going forward, just a safety copy from the 2026-09-04 restructure.

## Run

```bash
# First time: ./run.sh   (creates env, installs package + dev deps in editable mode)

source env/bin/activate

# Logger (connects to BMS at IP in cfg.ini)
python -m batterylogger.entrypoints.logger_main

# Analyzer (drag-and-drop CSV at http://localhost:8050)
python -m batterylogger.entrypoints.analyzer_main

# Tests
pytest --cov=batterylogger
```

**Startup connect-gate (2026-09-04):** the logger blocks quietly on `/api/bcs/home` every 2s (`LoggingUseCase.connect_retry_interval`) until it gets a real response — no CSV writing, no string polling, no status printing happen before that (previously these ran optimistically and printed "OFFLINE" placeholder rows while disconnected). Once connected, it *also* waits for `/api/bcs/info` + `/api/bcs/config` (existing 5-retry/~30s backoff, unchanged) before the first CSV row — deliberately kept, so every row has complete metadata from the start; a slow/429-ing BMS on those two endpoints delays first-row logging even though live telemetry is already flowing. Ctrl+C works at any point in this sequence (`LoggingUseCase.wait_until_connected()`).
## Key files

| File | Role |
|------|------|
| `src/batterylogger/domain/entities.py` | `BatteryReading` (frozen) + pure `apply_update()` merge |
| `src/batterylogger/domain/calculations.py` | Pure math: corrected vcell, cell IR, energy accumulation |
| `src/batterylogger/domain/cycle_analysis.py` | `detect_cycles(df)` — pandas allowed here by design (see doc) |
| `src/batterylogger/domain/stats.py` | `compute_session_stats(df, prefix='')` — numbers only, no rendering |
| `src/batterylogger/domain/string_reading.py` | `StringReading` (frozen) + `detect_string_ids(df)` for per-string columns |
| `src/batterylogger/domain/ports.py` | Port interfaces (Protocol) — the DIP boundary |
| `src/batterylogger/application/logging_service.py` | `LoggingUseCase` — polling/CSV/status/alert orchestration |
| `src/batterylogger/application/analysis_service.py` | `AnalysisUseCase` — parse + analyze a log |
| `src/batterylogger/adapters/outbound/bms_http_client.py` | aiohttp BMS client (implements `BatteryApiPort`) |
| `src/batterylogger/adapters/outbound/csv_reading_writer.py` | CSV writer (implements `ReadingWriterPort`) |
| `src/batterylogger/adapters/outbound/ini_config_repository.py` | **Only** place that reads `cfg.ini` |
| `src/batterylogger/adapters/outbound/in_memory_state_repository.py` | Thread-safe live state (asyncio.Lock + domain calc) |
| `src/batterylogger/adapters/inbound/cli.py` | Logger CLI (argparse, signals, console output) |
| `src/batterylogger/adapters/inbound/dash_ui/` | Analyzer Dash app (layout/callbacks/charts/components) |
| `src/batterylogger/bootstrap/container.py` | Composition root — wires adapters into use-cases |
| `cfg.ini` | IP, poll rates, cell count, alert thresholds (repo root — resolved relative to cwd) |
| `run.sh` | Creates `env/`, `pip install -e ".[dev]"` |
| `tests/` | pytest suite — `unit/domain`, `unit/application`, `integration`, `smoke` |
| `doc/` | Additional documentation |

## BMS API endpoints

| Endpoint | Used for |
|----------|----------|
| `/api/bcs/home` | Pack-level live data (voltage, current, SOC, cells, temps, capacity counters) |
| `/api/bcs/info` | Firmware versions, serial numbers |
| `/api/bcs/config` | Battery model, topology, nominal capacity |
| `/api/bcs/string` | `stringInfo.discovered` — list of present string IDs, e.g. `[1, 2, 4]` (not necessarily contiguous). Fetched once at startup, like `/info`/`/config`. |
| `/api/bcs/battery/S{id:02d}` | Per-string live data (e.g. `S01`, `S04`) — same shape as `/home` plus `dispersion` + `event_mask`. Polled on its own slower `StringPollInterval` cadence, sequentially per string (the BMS already 429s under lighter load). |

## CSV columns to know

All `BatteryReading` fields are flattened with `_` separator (see `CsvReadingWriter._flatten`):

| Column | Meaning |
|--------|---------|
| `capacity_capacityChCurrentCycle` | Ah charged in ongoing charge cycle (resets to 0 when discharge starts) |
| `capacity_capacityDchCurrentCycle` | Ah discharged in ongoing discharge cycle (resets to 0 when charge starts) |
| `capacity_capacityChLastCycle` | Ah from last completed charge cycle |
| `capacity_capacityDchLastCycle` | Ah from last completed discharge cycle |
| `capacity_usefulCapacity` | BMS-reported usable capacity (≈ 266 Ah for 280 Ah cell) |
| `meta_capacity_ah` | Nominal capacity from config (280 Ah, constant) |
| `vcell_corrected_vcell` | IR-compensated cell voltage (derived in `domain/calculations.py`) |

**Per-string columns** (added when strings are discovered): every `StringReading` field flattened the same way, prefixed `string{id}_` — e.g. `string1_soc`, `string1_vcell_vcellMax`, `string1_dispersion_dispersionAvg`, `string1_event_mask_0..5`. Wide format: still one row per timestamp, pack-level columns unchanged. Old CSVs (pre this feature) simply have none of these columns — `domain/string_reading.py::detect_string_ids(df)` returns `[]` for them, and the analyzer renders no string tabs (fully backward compatible). The manual "Strings in parallel" selector in the Dash UI is unrelated/unchanged — it still only drives the cycle table's Ah/string split for those old logs.

## Cycle analysis (domain/cycle_analysis.py)

`detect_cycles(df)` segments the log into charge/discharge half-cycles by watching for resets in the BMS Ah counters. Validates each segment against mean current direction to handle BMS mid-cycle counter resets (observed behavior: BMS resets `capacityChCurrentCycle` without starting a discharge).

`detect_cycles()` returns `list[Cycle]` (frozen dataclass) — pure numbers, no
Dash/HTML. `adapters/inbound/dash_ui/components.py::build_cycle_table(cycles)`
renders that into a Bootstrap card with:
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

This table is enforced as a regression test: `tests/unit/domain/test_cycle_analysis.py::TestGoldenLog` runs `detect_cycles()` against `tests/fixtures/sample_log.csv` (a trimmed real log) and asserts 3 cycles, alternating discharge/charge/discharge, each ≥95% match.

## Config reference (cfg.ini)

```ini
[Battery_API]
IP=192.168.55.193
PollInterval=5          ; seconds between live polls
StringPollInterval=30   ; seconds between per-string polls (slower on purpose)

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

Runtime (`requirements.txt` / `pyproject.toml [project.dependencies]`):
```
aiohttp, dash, dash-bootstrap-components, pandas, plotly
```

Dev/test (`requirements-dev.txt` / `[project.optional-dependencies].dev`):
```
pytest, pytest-asyncio, pytest-cov, pytest-mock, aioresponses, freezegun
```

Python ≥ 3.10 required (uses `X | Y` union type hints). Package installed
editable via `pyproject.toml` (`pip install -e ".[dev]"`) — `run.sh` does this.
