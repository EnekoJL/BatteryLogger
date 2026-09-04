"""Charge/discharge cycle detection from a battery log.

Pandas is used here deliberately — it's the domain's native data structure
for time-series log analysis (same role NumPy plays in scientific code),
not a leaked infrastructure concern. No file I/O or network calls happen in
this module; `df` is handed in already parsed by an adapter.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

MIN_DELTA_SOC = 50.0  # ignore segments shallower than this (noise, brief balancing pulses)


@dataclass(frozen=True)
class Cycle:
    n: int
    kind: str  # 'charge' | 'discharge'
    t_start: datetime
    t_end: datetime
    duration: str
    soc_start: float
    soc_end: float
    delta_soc: float
    ah: float
    ah_calc: Optional[float]
    theo_ah: float | None
    match_pct: float | None
    useful_capacity: float
    nominal_capacity: float
    note: str


def detect_cycles(df: pd.DataFrame) -> list[Cycle]:
    """Segments a log into charge/discharge half-cycles.

    Boundaries are detected from large drops in capacityDchCurrentCycle /
    capacityChCurrentCycle (the BMS resets each counter when the opposite
    half-cycle begins). Each segment is validated against its dominant
    current direction to handle BMS mid-cycle counter resets (observed:
    BMS resets capacityChCurrentCycle without starting a discharge).
    """
    required = {
        'capacity_capacityDchCurrentCycle',
        'capacity_capacityChCurrentCycle',
        'soc',
        'Timestamp',
    }
    if not required.issubset(df.columns):
        return []

    df = df.copy()
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)
    df = df.dropna(subset=['soc']).reset_index(drop=True)

    dch = df['capacity_capacityDchCurrentCycle']
    ch = df['capacity_capacityChCurrentCycle']

    dch_resets = df.index[(dch.diff().fillna(0) < -5)].tolist()
    ch_resets = df.index[(ch.diff().fillna(0) < -5)].tolist()

    events = (
        [(i, 'dch') for i in dch_resets] +
        [(i, 'ch') for i in ch_resets]
    )
    events.sort(key=lambda e: e[0])

    bounds = [0] + [e[0] for e in events] + [len(df)]

    def _seg_kind(k: int) -> str:
        if k < len(events):
            return 'discharge' if events[k][1] == 'dch' else 'charge'
        if events:
            return 'charge' if events[-1][1] == 'dch' else 'discharge'
        return 'charge' if ch.max() >= dch.max() else 'discharge'

    useful_cap = float(df['capacity_usefulCapacity'].iloc[0]) if 'capacity_usefulCapacity' in df.columns else 0.0
    nominal_cap = float(df['meta_capacity_ah'].iloc[0]) if 'meta_capacity_ah' in df.columns else 0.0

    cycles: list[Cycle] = []

    for k in range(len(bounds) - 1):
        si, ei = bounds[k], bounds[k + 1] - 1
        seg = df.iloc[si:ei + 1]
        if len(seg) < 2:
            continue

        if abs(float(seg['soc'].iloc[0]) - float(seg['soc'].iloc[-1])) < MIN_DELTA_SOC:
            continue

        kind = _seg_kind(k)

        # Validate against dominant current direction: overrides if BMS reset counter
        # mid-cycle (e.g. BMS restarts its Ah counter without changing direction)
        if 'current' in df.columns and len(seg) >= 3:
            mean_cur = float(df['current'].iloc[si:ei + 1].mean())
            current_kind = 'charge' if mean_cur > 0 else 'discharge'
            if current_kind != kind:
                kind = current_kind

        ah = float(dch.iloc[si:ei + 1].max() if kind == 'discharge' else ch.iloc[si:ei + 1].max())

        # Coulombometry: ∫ |I| dt / 3600  (independent of BMS counter)
        if 'current' in df.columns:
            seg_cur = df['current'].iloc[si:ei + 1].values
            seg_ts = df['Timestamp'].iloc[si:ei + 1]
            dt_s = seg_ts.diff().dt.total_seconds().fillna(0).values
            ah_calc = float(abs((seg_cur * dt_s).sum()) / 3600.0)
        else:
            ah_calc = None

        soc_start = float(seg['soc'].iloc[0])
        soc_end = float(seg['soc'].iloc[-1])
        delta_soc = abs(soc_start - soc_end)
        t_start = seg['Timestamp'].iloc[0]
        t_end = seg['Timestamp'].iloc[-1]
        dur_s = int((t_end - t_start).total_seconds())
        hh, rem = divmod(dur_s, 3600)
        mm, ss = divmod(rem, 60)

        # First segment partial if counter already had a non-zero value at log start
        partial_start = k == 0 and (
            (kind == 'charge' and float(ch.iloc[si]) > 5) or
            (kind == 'discharge' and float(dch.iloc[si]) > 5)
        )
        partial_end = k == len(events)

        note_parts = []
        if partial_start:
            note_parts.append('Partial (log start)')
        if partial_end:
            note_parts.append('Partial (log end)')

        theo_ah = useful_cap * delta_soc / 100.0 if useful_cap > 0 else None
        match_pct = (ah / theo_ah * 100.0) if (theo_ah and theo_ah > 0 and not partial_start and not partial_end) else None

        cycles.append(Cycle(
            n=k + 1,
            kind=kind,
            t_start=t_start,
            t_end=t_end,
            duration=f'{hh:02d}:{mm:02d}:{ss:02d}',
            soc_start=round(soc_start, 1),
            soc_end=round(soc_end, 1),
            delta_soc=round(delta_soc, 1),
            ah=round(ah, 1),
            ah_calc=round(ah_calc, 1) if ah_calc is not None else None,
            theo_ah=round(theo_ah, 1) if theo_ah is not None else None,
            match_pct=round(match_pct, 1) if match_pct is not None else None,
            useful_capacity=useful_cap,
            nominal_capacity=nominal_cap,
            note=' · '.join(note_parts),
        ))

    return cycles
