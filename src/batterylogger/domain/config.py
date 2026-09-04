"""Small config value objects — what the domain/application need from cfg.ini,
without caring how or where it's stored (that's ConfigPort's job)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    base_url: str
    poll_interval: int = 2
    string_poll_interval: int = 30


@dataclass(frozen=True)
class LoggerSettings:
    log_frequency: int = 60
    rotate_daily: bool = True


@dataclass(frozen=True)
class BatteryTopology:
    num_cells: int = 15
    num_modules: int = 1


@dataclass(frozen=True)
class AlertThresholds:
    soc_low: float = 20.0
    temp_high: float = 40.0
