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


def compute_session_stats(df: pd.DataFrame) -> SessionStats:
    kwargs = {'record_count': len(df)}

    if 'Timestamp' in df.columns:
        ts = pd.to_datetime(df['Timestamp'])
        total_s = int((ts.max() - ts.min()).total_seconds())
        h, rem = divmod(total_s, 3600)
        m, s = divmod(rem, 60)
        kwargs['duration_str'] = f'{h:02d}:{m:02d}:{s:02d}'

    if 'soc' in df.columns:
        kwargs['soc_min'] = float(df['soc'].min())
        kwargs['soc_max'] = float(df['soc'].max())
        kwargs['biggest_soc_jump_pct'] = float(df['soc'].diff().abs().max())

    if 'temperature_tempMax' in df.columns:
        kwargs['max_temp'] = float(df['temperature_tempMax'].max())

    if 'current' in df.columns:
        peak_ch = float(df['current'].max())
        peak_dch = float(df['current'].min())
        if peak_ch > 0:
            kwargs['peak_charge_a'] = peak_ch
        if peak_dch < 0:
            kwargs['peak_discharge_a'] = abs(peak_dch)

    if 'vcell_vcellMax' in df.columns:
        kwargs['max_cell_v'] = float(df['vcell_vcellMax'].max())
    if 'vcell_vcellMin' in df.columns:
        kwargs['min_cell_v'] = float(df['vcell_vcellMin'].min())
    if 'vcell_vcellMax' in df.columns and 'vcell_vcellMin' in df.columns:
        kwargs['max_cell_spread_mv'] = float((df['vcell_vcellMax'] - df['vcell_vcellMin']).max())

    if 'vcell_internalResistance' in df.columns:
        kwargs['max_pack_ir'] = float(df['vcell_internalResistance'].max())

    if 'temperature_tempMax' in df.columns and 'temperature_tempMin' in df.columns:
        kwargs['max_temp_spread'] = float((df['temperature_tempMax'] - df['temperature_tempMin']).max())

    return SessionStats(**kwargs)
