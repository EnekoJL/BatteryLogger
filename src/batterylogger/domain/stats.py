"""Session-level summary numbers for a battery log — no presentation here."""

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class SessionStats:
    duration_str: Optional[str] = None
    record_count: int = 0
    soc_min: Optional[float] = None
    soc_max: Optional[float] = None
    max_temp: Optional[float] = None
    peak_charge_a: Optional[float] = None
    peak_discharge_a: Optional[float] = None
    max_cell_v: Optional[float] = None
    min_cell_v: Optional[float] = None
    max_cell_spread_mv: Optional[float] = None
    biggest_soc_jump_pct: Optional[float] = None
    max_pack_ir: Optional[float] = None
    max_temp_spread: Optional[float] = None


def compute_session_stats(df: pd.DataFrame, prefix: str = '') -> SessionStats:
    """`prefix=''` reads pack-level columns; `prefix='string1_'` reads that
    string's columns instead — same stats, reused for per-string tabs
    (`Timestamp` is never prefixed, it's the shared time axis)."""
    def col(name: str) -> str:
        return f'{prefix}{name}'

    kwargs = {'record_count': len(df)}

    if 'Timestamp' in df.columns:
        ts = pd.to_datetime(df['Timestamp'])
        total_s = int((ts.max() - ts.min()).total_seconds())
        h, rem = divmod(total_s, 3600)
        m, s = divmod(rem, 60)
        kwargs['duration_str'] = f'{h:02d}:{m:02d}:{s:02d}'

    if col('soc') in df.columns:
        kwargs['soc_min'] = float(df[col('soc')].min())
        kwargs['soc_max'] = float(df[col('soc')].max())
        kwargs['biggest_soc_jump_pct'] = float(df[col('soc')].diff().abs().max())

    if col('temperature_tempMax') in df.columns:
        kwargs['max_temp'] = float(df[col('temperature_tempMax')].max())

    if col('current') in df.columns:
        peak_ch = float(df[col('current')].max())
        peak_dch = float(df[col('current')].min())
        if peak_ch > 0:
            kwargs['peak_charge_a'] = peak_ch
        if peak_dch < 0:
            kwargs['peak_discharge_a'] = abs(peak_dch)

    if col('vcell_vcellMax') in df.columns:
        kwargs['max_cell_v'] = float(df[col('vcell_vcellMax')].max())
    if col('vcell_vcellMin') in df.columns:
        kwargs['min_cell_v'] = float(df[col('vcell_vcellMin')].min())
    if col('vcell_vcellMax') in df.columns and col('vcell_vcellMin') in df.columns:
        kwargs['max_cell_spread_mv'] = float((df[col('vcell_vcellMax')] - df[col('vcell_vcellMin')]).max())

    if col('vcell_internalResistance') in df.columns:
        kwargs['max_pack_ir'] = float(df[col('vcell_internalResistance')].max())

    if col('temperature_tempMax') in df.columns and col('temperature_tempMin') in df.columns:
        kwargs['max_temp_spread'] = float((df[col('temperature_tempMax')] - df[col('temperature_tempMin')]).max())

    return SessionStats(**kwargs)
