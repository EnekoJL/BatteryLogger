# Architecture

Hexagonal (ports & adapters), restructured 2026-09-04 from a flat 5-file
script layout (preserved at `../BatteryLogger_v1_flat` and in git history).

## Layers

```
domain/        Entities, value objects, pure calculations, ports (interfaces).
               Zero I/O. Zero aiohttp/Dash/csv/configparser imports.
application/   Use-cases (LoggingUseCase, AnalysisUseCase) — orchestrate
               ports. No concrete adapter imports.
adapters/
  inbound/      Driving adapters: CLI (logger), Dash UI (analyzer).
  outbound/     Driven adapters: aiohttp BMS client, CSV read/write,
                cfg.ini repository, in-memory state store, console alerts.
bootstrap/     Composition root (container.py) — the only module that
               imports both domain.ports AND concrete adapter classes.
entrypoints/   Thin `python -m` shims: build container, call the adapter.
```

Dependency direction is always inward: `adapters` → `application` → `domain`.
Nothing in `domain/` or `application/` imports from `adapters/` or
`bootstrap/`.

## Why each layer exists (SOLID mapping)

- **SRP** — `bms_http_client.py` and `csv_reading_writer.py` no longer parse
  `cfg.ini` themselves (the old `api_controller.py`/`csv_writer.py` each had
  their own duplicated `_load_config`). Config parsing lives in exactly one
  place: `adapters/outbound/ini_config_repository.py`.
- **OCP** — swapping CSV storage for, say, a database later means writing a
  new `ReadingWriterPort` adapter. `LoggingUseCase` doesn't change.
- **LSP** — every adapter is exercised against its port's contract via fake
  adapters built in `tests/conftest.py` (`FakeBatteryApi`, `FakeWriter`, …)
  that satisfy the same `Protocol` the real adapter does.
- **ISP** — `ReadingWriterPort` (logger, write-only) and `ReadingParserPort`
  (analyzer, read-only) are separate interfaces; the analyzer never depends
  on write methods it doesn't use.
- **DIP** — `application/` and `domain/` depend only on `domain/ports.py`
  (`Protocol` interfaces — structural typing, no inheritance required).
  `bootstrap/container.py` is the single place a concrete adapter (e.g.
  `AiohttpBmsClient`) gets wired to a use-case.

## Deliberate trade-off: pandas in the domain layer

Strict hexagonal architecture keeps the domain framework-free. Here,
`domain/cycle_analysis.py` (`detect_cycles`) and `domain/stats.py`
(`compute_session_stats`) use pandas `DataFrame` as their working data
structure — chosen deliberately over rewriting the (proven, vectorized)
cycle-detection math as pure Python loops over `list[BatteryReading]`.

Reasoning: pandas here plays the role NumPy plays in scientific code — a
computation tool, not an infrastructure concern. The boundary that actually
matters for hexagonal architecture (no aiohttp, no Dash, no file I/O, no
configparser inside `domain/`) is still fully respected. A rewrite to pure
Python would have meant re-deriving a working algorithm against a real BMS's
quirky counter-reset behavior, with real regression risk, for a purity gain
with no practical benefit at this project's scale (logs are single-machine
CSV files, not a distributed pipeline where dropping pandas would matter).

If this trade-off ever needs revisiting (e.g. domain logic needs to run
somewhere pandas isn't available), `domain/cycle_analysis.py` and
`domain/stats.py` are the only two files affected.

## Concurrency placement

`BatteryReading` and its nested value objects are frozen dataclasses —
immutable. The only mutable, lock-guarded state is
`adapters/outbound/in_memory_state_repository.py::InMemoryStateRepository`,
which wraps the pure `domain.entities.apply_update()` /
`domain.calculations.compute_derived_vcell()` / `accumulate_energy()`
functions with an `asyncio.Lock`. Concurrency control is treated as an
infrastructure concern, not a domain one — the domain functions themselves
have no async/threading awareness at all.

## Testing

See the top-level README's Testing section. Coverage is concentrated on
`domain/` and `application/` (near 100%) since that's where the business
logic lives; thin wiring (`cli.py`, `bootstrap/container.py`,
`entrypoints/*`, Dash `app.py`/`layout.py`) is verified by manual/smoke
testing instead — testing argparse wiring or a Dash app factory adds little
beyond what an end-to-end run already confirms.
