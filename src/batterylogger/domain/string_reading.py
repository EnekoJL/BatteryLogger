"""Per-string BMS telemetry: `/api/bcs/battery/S{id:02d}` — same shape as
the pack-level home payload, plus `dispersion` and `event_mask` sections not
present at pack level.

No I/O here — HTTP fetching lives in adapters/outbound/bms_http_client.py,
CSV column naming (`string{id}_...`) lives in
adapters/outbound/csv_reading_writer.py, tab rendering in
adapters/inbound/dash_ui/components.py.
"""

import re
from dataclasses import dataclass, field

import pandas as pd

from batterylogger.domain.entities import AgingData, CapacityData, SopData, TemperatureData, VCellData
from batterylogger.domain.merge import merge_dataclass

_STRING_COLUMN_RE = re.compile(r'^string(\d+)_soc$')


@dataclass(frozen=True)
class DispersionData:
    dispersionMax: float = 0.0
    dispersionMaxMcl: int = 0
    dispersionMin: float = 0.0
    dispersionMinMcl: int = 0
    dispersionAvg: float = 0.0


@dataclass(frozen=True)
class StringReading:
    id: str = ""
    AñoSemana: int = 0
    Ordinal: int = 0
    serial: int = 0
    full_serial: str = ""
    comms: int = 0
    mode_req: int = 0
    mode_req_str: str = ""
    state_req: int = 0
    state_req_str: str = ""
    state: int = 0
    state_str: str = ""
    status: int = 0
    operation: int = 0
    operation_str: str = ""
    mode: int = 0
    mode_str: str = ""
    special_mode_str: str = ""
    current: float = 0.0
    voltage: float = 0.0
    voltage_sensor: float = 0.0
    soc: float = 0.0
    soh: float = 0.0
    power: float = 0.0
    sop: SopData = field(default_factory=SopData)
    aging: AgingData = field(default_factory=AgingData)
    capacity: CapacityData = field(default_factory=CapacityData)
    vcell: VCellData = field(default_factory=VCellData)
    dispersion: DispersionData = field(default_factory=DispersionData)
    temperature: TemperatureData = field(default_factory=TemperatureData)
    # Fixed-length (BMS always returns 6 flags) so a default StringReading()
    # flattens to a stable set of event_mask_0..5 CSV columns even before
    # any real string data has arrived — see CsvReadingWriter.configure().
    event_mask: list[int] = field(default_factory=lambda: [0] * 6)

    def __str__(self) -> str:
        return (
            f"=== String {self.id} ===\n"
            f"  State: {self.state_str} | Mode: {self.mode_str}\n"
            f"  Voltage: {self.voltage:.2f}V | Current: {self.current:.1f}A | Power: {self.power:.0f}W\n"
            f"  SOC: {self.soc:.1f}% | SOH: {self.soh:.1f}%"
        )


def apply_string_update(reading: StringReading, patch: dict) -> StringReading:
    """Pure merge: returns a new StringReading with `patch` applied on top
    (the raw `batteryInfo` object from `/api/bcs/battery/Sxx`)."""
    return merge_dataclass(reading, patch)


def detect_string_ids(df: pd.DataFrame) -> list[int]:
    """Which string IDs a (possibly old-format) log has columns for.

    Empty list means an old CSV that predates per-string logging — callers
    should render nothing extra (fully backward compatible).
    """
    ids = []
    for col in df.columns:
        match = _STRING_COLUMN_RE.match(col)
        if match:
            ids.append(int(match.group(1)))
    return sorted(ids)
