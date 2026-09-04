"""Immutable value objects describing static BMS/device metadata."""

from dataclasses import dataclass


@dataclass(frozen=True)
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
        return f"MCS={self.mcs_core}{scs} | Serial={self.full_serial} | Update={self.update_status}"


@dataclass(frozen=True)
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
