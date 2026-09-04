import asyncio
import csv
import configparser
import logging
import os
from datetime import datetime, date
from datastruct import BatteryData, BatteryInfo, FirmwareInfo, BatteryConfig

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


class CSVWriter:
    def __init__(
        self,
        battery_data: BatteryData,
        firmware_info: FirmwareInfo | None = None,
        battery_config: BatteryConfig | None = None,
        config_path: str = 'cfg.ini',
    ):
        self.battery_data = battery_data
        self.firmware_info = firmware_info or FirmwareInfo()
        self.battery_config = battery_config or BatteryConfig()
        self.config_path = config_path
        self.frequency: int = 60
        self.rotate_daily: bool = True
        self.running: bool = False
        self.filename: str = ""
        self._headers: list[str] | None = None
        self._static_meta: dict | None = None
        self._records_written: int = 0
        self._session_start: datetime | None = None
        self._current_date: date | None = None
        self._load_config()

    def _load_config(self):
        config = configparser.ConfigParser()
        if not os.path.exists(self.config_path):
            logger.error(f"Config file not found: {self.config_path}")
            return
        config.read(self.config_path)
        try:
            self.frequency = int(config['Logging']['LogFrequency'])
            self.rotate_daily = config['Logging'].getboolean('RotateDaily', fallback=True)
            logger.info(
                f"CSV log frequency: {self.frequency}s | "
                f"Daily rotation: {'on' if self.rotate_daily else 'off'}"
            )
        except KeyError as e:
            logger.warning(f"Missing logging config, using defaults: {e}")
        except ValueError:
            logger.error("Invalid LogFrequency in config.")

    def _build_static_meta(self) -> dict:
        fw = self.firmware_info
        cfg = self.battery_config
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
                else:
                    items[new_key] = value
        return items

    def _csv_dir(self) -> str:
        base = os.path.dirname(os.path.abspath(self.config_path))
        return os.path.join(base, 'csv')

    def _create_file(self):
        os.makedirs(self._csv_dir(), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_tag = (
            self.battery_config.battery_model.replace(' ', '_') or 'battery'
        )
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

    async def run_loop(self):
        self.running = True
        self._session_start = datetime.now()
        logger.info("Starting CSV writer loop...")

        # Wait for first real data
        await asyncio.sleep(3)

        snapshot = await self.battery_data.get_snapshot()
        live_fields = list(self._flatten(snapshot).keys())
        self._headers = ['Timestamp'] + _STATIC_META_COLUMNS + live_fields
        self._static_meta = self._build_static_meta()
        self._current_date = datetime.now().date()
        self._create_file()

        while self.running:
            try:
                now = datetime.now()

                if self.rotate_daily and now.date() != self._current_date:
                    self._current_date = now.date()
                    self._create_file()
                    logger.info("Daily log rotation: new file started.")

                snapshot = await self.battery_data.get_snapshot()

                if snapshot.voltage <= 0:
                    logger.debug("Skipping row: voltage=0 (no live data yet)")
                else:
                    row = {
                        'Timestamp': now.strftime("%Y-%m-%d %H:%M:%S"),
                        **self._static_meta,
                        **self._flatten(snapshot),
                    }
                    if self.filename:
                        with open(self.filename, 'a', newline='', encoding='utf-8-sig') as f:
                            csv.DictWriter(f, fieldnames=self._headers).writerow(row)
                        self._records_written += 1
                        logger.debug(f"Logged row #{self._records_written}")

            except IOError as e:
                logger.error(f"CSV write error: {e}")
            except Exception as e:
                logger.error(f"Unexpected CSV error: {e}")

            await asyncio.sleep(self.frequency)

    def stop(self):
        self.running = False
        if self._session_start:
            duration = datetime.now() - self._session_start
            h, rem = divmod(int(duration.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            logger.info(
                f"CSV writer stopped | Records: {self._records_written} | "
                f"Duration: {h:02d}:{m:02d}:{s:02d} | File: {self.filename}"
            )
        else:
            logger.info("CSV writer stopped (never started).")

    @property
    def records_written(self) -> int:
        return self._records_written
