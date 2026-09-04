import asyncio
import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class FirmwareInfo:
    mcs_core: str = ""
    mcs_platform: str = ""
    mcs_system: str = ""
    full_serial: str = ""
    serial: int = 0
    update_status: str = ""
    scs_core: str = ""
    scs_serial: str = ""

    def __str__(self) -> str:
        scs = f" | SCS={self.scs_core}" if self.scs_core else ""
        return (
            f"MCS={self.mcs_core}{scs} | Serial={self.full_serial} | Update={self.update_status}"
        )


@dataclass
class BatteryConfig:
    battery_model: str = ""
    strings_count: int = 0
    modules_per_string: int = 0
    nominal_capacity_ah: float = 0.0
    inverter_model: str = ""
    ip_address: str = ""

    def __str__(self) -> str:
        return (
            f"Model={self.battery_model} | "
            f"Strings={self.strings_count}x{self.modules_per_string} modules | "
            f"Capacity={self.nominal_capacity_ah}Ah | "
            f"Inverter={self.inverter_model}"
        )


@dataclass
class SopData:
    vCh: float = 0.0
    vDisch: float = 0.0
    iCh: float = 0.0
    iDisch: float = 0.0
    allow_ch: int = 0
    allow_dch: int = 0
    enable_ch: int = 0
    enable_dch: int = 0


@dataclass
class AgingData:
    equivalentTotalCicles: float = 0.0
    calendarTotal: float = 0.0
    calendarNormal: float = 0.0
    calendarCold: float = 0.0
    calendarWarm: float = 0.0
    calendarCrateAbove55: float = 0.0
    calendarCrateAbove75: float = 0.0
    efficiency: float = 0.0


@dataclass
class CapacityData:
    usefulCapacity: float = 0.0
    capacityChCurrentCycle: float = 0.0
    capacityDchCurrentCycle: float = 0.0
    capacityChLastCycle: float = 0.0
    capacityDchLastCycle: float = 0.0
    capacityChAcum: float = 0.0
    capacityDchAcum: float = 0.0


@dataclass
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


@dataclass
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


@dataclass
class BatteryInfo:
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


class BatteryData:
    def __init__(self, num_cells: int = 15, num_modules: int = 1):
        self._lock = asyncio.Lock()
        self._data = BatteryInfo()
        self.num_cells = num_cells
        self.num_modules = num_modules
        self._energy_ch_wh: float = 0.0
        self._energy_dch_wh: float = 0.0
        self._last_update_time: Optional[datetime] = None

    async def update(self, **kwargs):
        async with self._lock:
            data_dict = kwargs.get('batteryInfo', kwargs)

            def update_dataclass(dc_instance, data: dict):
                for key, value in data.items():
                    if hasattr(dc_instance, key):
                        attr = getattr(dc_instance, key)
                        if hasattr(attr, '__dataclass_fields__') and isinstance(value, dict):
                            update_dataclass(attr, value)
                        else:
                            setattr(dc_instance, key, value)

            update_dataclass(self._data, data_dict)
            self._compute_derived()
            self._accumulate_energy()

    def _compute_derived(self):
        if self.num_cells > 0:
            total_cells = self.num_cells * self.num_modules
            self._data.vcell.cellInternalResistance = (
                self._data.vcell.internalResistance / total_cells
            )
            r_cell = self._data.vcell.cellInternalResistance
            drop = abs(self._data.current) * r_cell
            if self._data.current < 0:
                self._data.vcell.corrected_vcell = self._data.vcell.vcellMin + drop
            else:
                self._data.vcell.corrected_vcell = self._data.vcell.vcellMax - drop
        else:
            self._data.vcell.cellInternalResistance = 0.0
            self._data.vcell.corrected_vcell = 0.0

    def _accumulate_energy(self):
        now = datetime.now()
        if self._last_update_time is not None and self._data.power != 0:
            dt_h = (now - self._last_update_time).total_seconds() / 3600.0
            if self._data.power > 0:
                self._energy_ch_wh += self._data.power * dt_h
            else:
                self._energy_dch_wh += abs(self._data.power) * dt_h
        self._last_update_time = now

    async def get_snapshot(self) -> BatteryInfo:
        async with self._lock:
            return copy.deepcopy(self._data)

    async def get_energy_stats(self) -> dict:
        async with self._lock:
            return {
                'energy_ch_wh': round(self._energy_ch_wh, 3),
                'energy_dch_wh': round(self._energy_dch_wh, 3),
            }
