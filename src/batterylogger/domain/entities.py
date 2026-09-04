"""Core battery reading entity and the pure merge logic that updates it.

No I/O, no asyncio, no framework imports here. Concurrency (locking) is an
infrastructure concern and lives in adapters/outbound/in_memory_state_repository.py.
"""

from dataclasses import dataclass, field

from batterylogger.domain.merge import merge_dataclass


@dataclass(frozen=True)
class SopData:
    vCh: float = 0.0
    vDisch: float = 0.0
    iCh: float = 0.0
    iDisch: float = 0.0
    allow_ch: int = 0
    allow_dch: int = 0
    enable_ch: int = 0
    enable_dch: int = 0


@dataclass(frozen=True)
class AgingData:
    equivalentTotalCicles: float = 0.0
    calendarTotal: float = 0.0
    calendarNormal: float = 0.0
    calendarCold: float = 0.0
    calendarWarm: float = 0.0
    calendarCrateAbove55: float = 0.0
    calendarCrateAbove75: float = 0.0
    efficiency: float = 0.0


@dataclass(frozen=True)
class CapacityData:
    usefulCapacity: float = 0.0
    capacityChCurrentCycle: float = 0.0
    capacityDchCurrentCycle: float = 0.0
    capacityChLastCycle: float = 0.0
    capacityDchLastCycle: float = 0.0
    capacityChAcum: float = 0.0
    capacityDchAcum: float = 0.0


@dataclass(frozen=True)
class VCellData:
    vcellMax: int = 0
    vcellMaxRaw: int = 0
    vcellMaxCcl: int = 0
    vcellMaxMcl: int = 0
    vcellMaxScl: int = 0
    vcellMin: int = 0
    vcellMinRaw: int = 0
    vcellMinCcl: int = 0
    vcellMinMcl: int = 0
    vcellMinScl: int = 0
    vcellAvg: int = 0
    vcellAvgRaw: int = 0
    internalResistance: float = 0.0
    cellInternalResistance: float = 0.0
    corrected_vcell: float = 0.0


@dataclass(frozen=True)
class TemperatureData:
    tempMax: float = 0.0
    tempMaxCcl: int = 0
    tempMaxMcl: int = 0
    tempMaxScl: int = 0
    tempMin: float = 0.0
    tempMinCcl: int = 0
    tempMinMcl: int = 0
    tempMinScl: int = 0
    FanTime_h: int = 0
    tempAmb: float = 0.0
    tempPCB: float = 0.0


@dataclass(frozen=True)
class BatteryReading:
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
    temperature: TemperatureData = field(default_factory=TemperatureData)

    def __str__(self) -> str:
        return (
            f"=== Battery {self.id} ===\n"
            f"  State: {self.state_str} | Mode: {self.mode_str}\n"
            f"  Voltage: {self.voltage:.2f}V | Current: {self.current:.1f}A | Power: {self.power:.0f}W\n"
            f"  SOC: {self.soc:.1f}% | SOH: {self.soh:.1f}%\n"
            f"  Cells: Max {self.vcell.vcellMax}mV | Min {self.vcell.vcellMin}mV | Avg {self.vcell.vcellAvg}mV\n"
            f"  Temps: Max {self.temperature.tempMax:.1f}°C | Min {self.temperature.tempMin:.1f}°C | Amb {self.temperature.tempAmb:.1f}°C\n"
            f"  Corrected VCell: {self.vcell.corrected_vcell:.1f}mV | Cell IR: {self.vcell.cellInternalResistance:.3f}mΩ"
        )


@dataclass(frozen=True)
class SessionSummary:
    filename: str = ""
    records_written: int = 0
    duration_s: int = 0


def apply_update(reading: BatteryReading, patch: dict) -> BatteryReading:
    """Pure merge: returns a new BatteryReading with `patch` applied on top.

    `patch` may be a flat dict of top-level fields, or nest dicts for
    `sop`/`aging`/`capacity`/`vcell`/`temperature` — matching the raw
    `/api/bcs/home` JSON shape.
    """
    return merge_dataclass(reading, patch)
