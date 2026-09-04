"""Single source of truth for reading cfg.ini.

Previously this parsing was duplicated across api_controller.py and
csv_writer.py (each with its own `_load_config`), plus ad-hoc parsing
in main_logger.py for battery topology and alert thresholds — a clear
SRP violation. Everything cfg.ini-shaped now lives here, behind ConfigPort.
"""

import configparser
import logging
import os

from batterylogger.domain.config import (
    AlertThresholds,
    ApiSettings,
    BatteryTopology,
    LoggerSettings,
)

logger = logging.getLogger(__name__)


class IniConfigRepository:
    """Implements domain.ports.ConfigPort."""

    def __init__(self, config_path: str = 'cfg.ini'):
        self.config_path = config_path
        self._config = configparser.ConfigParser()
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
        else:
            self._config.read(config_path)

    def load_api_settings(self) -> ApiSettings:
        section = self._config['Battery_API'] if 'Battery_API' in self._config else {}
        ip = section.get('IP', '')
        poll_interval = int(section.get('PollInterval', 2))
        return ApiSettings(base_url=f"http://{ip}" if ip else "", poll_interval=poll_interval)

    def load_logger_settings(self) -> LoggerSettings:
        section = self._config['Logging'] if 'Logging' in self._config else {}
        try:
            frequency = int(section.get('LogFrequency', 60))
        except ValueError:
            logger.error("Invalid LogFrequency in config, using default (60s).")
            frequency = 60
        rotate_daily = self._config.getboolean('Logging', 'RotateDaily', fallback=True) if 'Logging' in self._config else True
        return LoggerSettings(log_frequency=frequency, rotate_daily=rotate_daily)

    def load_battery_topology(self) -> BatteryTopology:
        section = self._config['Battery_Config'] if 'Battery_Config' in self._config else {}
        return BatteryTopology(
            num_cells=int(section.get('NumCells', 15)),
            num_modules=int(section.get('NumModules', 1)),
        )

    def load_alert_thresholds(self) -> AlertThresholds:
        defaults = AlertThresholds()
        if 'Alerts' not in self._config:
            return defaults
        section = self._config['Alerts']
        return AlertThresholds(
            soc_low=float(section.get('SocLowThreshold', defaults.soc_low)),
            temp_high=float(section.get('TempHighThreshold', defaults.temp_high)),
        )
