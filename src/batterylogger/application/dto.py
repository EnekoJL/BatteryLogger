"""Use-case result objects — orchestration-specific, unlike domain/config.py's
config value objects which the domain itself needs."""

from dataclasses import dataclass, field
from typing import Optional

from batterylogger.domain.calculations import EnergyStats
from batterylogger.domain.cycle_analysis import Cycle
from batterylogger.domain.entities import BatteryReading, SessionSummary
from batterylogger.domain.stats import SessionStats
from batterylogger.domain.string_reading import StringReading
from batterylogger.domain.value_objects import BatteryConfig, FirmwareInfo


@dataclass(frozen=True)
class DryRunResult:
    ok: bool
    firmware: FirmwareInfo = FirmwareInfo()
    battery_config: BatteryConfig = BatteryConfig()
    reading: Optional[BatteryReading] = None
    error: Optional[str] = None
    discovered_strings: list[int] = field(default_factory=list)
    string_readings: dict[int, StringReading] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionReport:
    duration_s: int
    total_polls: int
    error_rate: float
    energy: EnergyStats
    csv_summary: Optional[SessionSummary] = None


@dataclass(frozen=True)
class AnalysisResult:
    stats: Optional[SessionStats]
    cycles: list[Cycle]
    error: Optional[str] = None
