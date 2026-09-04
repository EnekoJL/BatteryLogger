"""CSV persistence for live battery readings (logger side, write-only).

Config loading removed from here — `rotate_daily` is injected via
LoggerSettings (from ConfigPort), not parsed by this class directly
(that was the old csv_writer.py's SRP violation, duplicated with
api_controller.py's own `_load_config`).
"""

import csv
import logging
import os
from datetime import date, datetime
from typing import Optional

from batterylogger.domain.entities import BatteryReading, SessionSummary
from batterylogger.domain.string_reading import StringReading
from batterylogger.domain.value_objects import BatteryConfig, FirmwareInfo

logger = logging.getLogger(__name__)

_STATIC_META_COLUMNS = [
    'meta_mcs_fw',
    'meta_scs_fw',
    'meta_mcs_serial',
    'meta_scs_serial',
    'meta_battery_model',
    'meta_strings',
    'meta_modules_per_string',
    'meta_capacity_ah',
    'meta_inverter',
]


class CsvReadingWriter:
    """Implements domain.ports.ReadingWriterPort."""

    def __init__(self, rotate_daily: bool, config_path: str = 'cfg.ini'):
        self.rotate_daily = rotate_daily
        self.config_path = config_path
        self.filename: str = ""
        self._firmware = FirmwareInfo()
        self._battery_config = BatteryConfig()
        self._headers: Optional[list[str]] = None
        self._static_meta: Optional[dict] = None
        self._records_written: int = 0
        self._session_start: Optional[datetime] = None
        self._current_date: Optional[date] = None
        self._discovered_strings: list[int] = []

    def configure(
        self,
        firmware: FirmwareInfo,
        battery_config: BatteryConfig,
        discovered_strings: Optional[list[int]] = None,
    ) -> None:
        self._firmware = firmware
        self._battery_config = battery_config
        self._discovered_strings = discovered_strings or []

    def _build_static_meta(self) -> dict:
        fw = self._firmware
        cfg = self._battery_config
        return {
            'meta_mcs_fw': fw.mcs_core,
            'meta_scs_fw': fw.scs_core,
            'meta_mcs_serial': fw.full_serial,
            'meta_scs_serial': fw.scs_serial,
            'meta_battery_model': cfg.battery_model,
            'meta_strings': cfg.strings_count,
            'meta_modules_per_string': cfg.modules_per_string,
            'meta_capacity_ah': cfg.nominal_capacity_ah,
            'meta_inverter': cfg.inverter_model,
        }

    def _flatten(self, data: object, parent_key: str = '', sep: str = '_') -> dict:
        items = {}
        if hasattr(data, '__dataclass_fields__'):
            for field_name in data.__dataclass_fields__:
                value = getattr(data, field_name)
                new_key = f"{parent_key}{sep}{field_name}" if parent_key else field_name
                if hasattr(value, '__dataclass_fields__'):
                    items.update(self._flatten(value, new_key, sep=sep))
                elif isinstance(value, (list, tuple)):
                    for i, item in enumerate(value):
                        items[f"{new_key}{sep}{i}"] = item
                else:
                    items[new_key] = value
        return items

    def _csv_dir(self) -> str:
        base = os.path.dirname(os.path.abspath(self.config_path))
        return os.path.join(base, 'csv')

    def _create_file(self) -> None:
        os.makedirs(self._csv_dir(), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_tag = self._battery_config.battery_model.replace(' ', '_') or 'battery'
        self.filename = os.path.join(
            self._csv_dir(),
            f"battery_log_{model_tag}_{timestamp}.csv",
        )
        try:
            with open(self.filename, 'w', newline='', encoding='utf-8-sig') as f:
                csv.DictWriter(f, fieldnames=self._headers).writeheader()
            logger.info(f"CSV log file: {self.filename}")
        except IOError as e:
            logger.error(f"Failed to create CSV file: {e}")
            self.filename = ""

    def write(
        self,
        reading: BatteryReading,
        timestamp: datetime,
        string_readings: Optional[dict[int, StringReading]] = None,
    ) -> None:
        string_readings = string_readings or {}

        if self._headers is None:
            self._session_start = timestamp
            live_fields = list(self._flatten(reading).keys())
            string_fields = []
            for sid in self._discovered_strings:
                string_fields += list(self._flatten(StringReading(), parent_key=f'string{sid}').keys())
            self._headers = ['Timestamp'] + _STATIC_META_COLUMNS + live_fields + string_fields
            self._static_meta = self._build_static_meta()
            self._current_date = timestamp.date()
            self._create_file()

        if self.rotate_daily and timestamp.date() != self._current_date:
            self._current_date = timestamp.date()
            self._create_file()
            logger.info("Daily log rotation: new file started.")

        if reading.voltage <= 0:
            logger.debug("Skipping row: voltage=0 (no live data yet)")
            return

        if not self.filename:
            return

        row = {
            'Timestamp': timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            **self._static_meta,
            **self._flatten(reading),
        }
        for sid in self._discovered_strings:
            string_reading = string_readings.get(sid, StringReading())
            row.update(self._flatten(string_reading, parent_key=f'string{sid}'))
        try:
            with open(self.filename, 'a', newline='', encoding='utf-8-sig') as f:
                csv.DictWriter(f, fieldnames=self._headers).writerow(row)
            self._records_written += 1
            logger.debug(f"Logged row #{self._records_written}")
        except IOError as e:
            logger.error(f"CSV write error: {e}")

    def close(self, now: datetime) -> SessionSummary:
        duration_s = int((now - self._session_start).total_seconds()) if self._session_start else 0
        return SessionSummary(
            filename=self.filename,
            records_written=self._records_written,
            duration_s=duration_s,
        )
