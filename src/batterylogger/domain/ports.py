"""Port interfaces — the contract between application/domain and the outside world.

`application/` and `domain/` depend only on these Protocols. Concrete adapters
(adapters/outbound/*) implement them; `bootstrap/container.py` is the only
place that wires a concrete adapter to a use-case. This is the Dependency
Inversion boundary (DIP) and lets tests substitute fakes with zero mocking
frameworks (Protocols are structurally typed — a fake just needs matching
method signatures, no inheritance required).
"""

from datetime import datetime
from typing import Optional, Protocol

import pandas as pd

from batterylogger.domain.calculations import EnergyStats
from batterylogger.domain.config import (
    AlertThresholds,
    ApiSettings,
    BatteryTopology,
    LoggerSettings,
)
from batterylogger.domain.entities import BatteryReading, SessionSummary
from batterylogger.domain.string_reading import StringReading
from batterylogger.domain.value_objects import BatteryConfig, FirmwareInfo


class BatteryApiPort(Protocol):
    """Driven port: talks to the physical BMS over its REST API."""

    async def fetch_static_info(self) -> Optional[tuple[FirmwareInfo, BatteryConfig]]:
        ...

    async def fetch_live_reading(self) -> Optional[dict]:
        """Raw `/api/bcs/home` JSON payload, or None on failure."""
        ...

    async def fetch_discovered_strings(self) -> Optional[list[int]]:
        """`/api/bcs/string` → `stringInfo.discovered`, or None on failure."""
        ...

    async def fetch_string_reading(self, string_id: int) -> Optional[dict]:
        """Raw `batteryInfo` from `/api/bcs/battery/S{string_id:02d}`, or None on failure."""
        ...


class BatteryStateRepository(Protocol):
    """Driven port: holds the current in-flight battery reading + derived energy stats."""

    async def update(self, patch: dict) -> BatteryReading:
        ...

    async def get_snapshot(self) -> BatteryReading:
        ...

    async def get_energy_stats(self) -> EnergyStats:
        ...


class StringStateRepository(Protocol):
    """Driven port: holds the current in-flight reading per discovered string."""

    async def update(self, string_id: int, patch: dict) -> StringReading:
        ...

    async def get_snapshot(self, string_id: int) -> Optional[StringReading]:
        ...

    async def get_all_snapshots(self) -> dict[int, StringReading]:
        ...


class ReadingWriterPort(Protocol):
    """Driven port: persists live readings (logger side, write-only)."""

    def configure(
        self,
        firmware: FirmwareInfo,
        battery_config: BatteryConfig,
        discovered_strings: Optional[list[int]] = None,
    ) -> None:
        ...

    def write(
        self,
        reading: BatteryReading,
        timestamp: datetime,
        string_readings: Optional[dict[int, StringReading]] = None,
    ) -> None:
        ...

    def close(self, now: datetime) -> SessionSummary:
        ...


class ReadingParserPort(Protocol):
    """Driven port: turns an uploaded CSV log into a DataFrame (analyzer side, read-only)."""

    def parse(self, contents_b64: str, filename: str) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        """Returns (dataframe, error_message) — exactly one is None."""
        ...


class ConfigPort(Protocol):
    """Driven port: reads cfg.ini (or any future config source)."""

    def load_api_settings(self) -> ApiSettings:
        ...

    def load_logger_settings(self) -> LoggerSettings:
        ...

    def load_battery_topology(self) -> BatteryTopology:
        ...

    def load_alert_thresholds(self) -> AlertThresholds:
        ...


class AlertNotifierPort(Protocol):
    """Driven port: raises alerts (console today, could be email/Slack later)."""

    def notify_low_soc(self, soc: float, threshold: float) -> None:
        ...

    def notify_high_temp(self, temp: float, threshold: float) -> None:
        ...


class ClockPort(Protocol):
    def now(self) -> datetime:
        ...


class SleeperPort(Protocol):
    async def sleep(self, seconds: float) -> None:
        ...
