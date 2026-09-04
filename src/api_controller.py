import asyncio
import aiohttp
import configparser
import logging
import os
from datastruct import BatteryData, FirmwareInfo, BatteryConfig

logger = logging.getLogger(__name__)

ENDPOINT_HOME = "/api/bcs/home"
ENDPOINT_INFO = "/api/bcs/info"
ENDPOINT_CONFIG = "/api/bcs/config"

_BACKOFF_SEQUENCE = (2, 4, 8, 16, 30)


class APIController:
    def __init__(self, battery_data: BatteryData, config_path: str = 'cfg.ini'):
        self.battery_data = battery_data
        self.config_path = config_path
        self.base_url: str = ""
        self.poll_interval: int = 2
        self.running: bool = False
        self.firmware_info = FirmwareInfo()
        self.battery_config = BatteryConfig()
        self.static_info_ready = asyncio.Event()
        self._connected: bool = False
        self._error_count: int = 0
        self._total_polls: int = 0
        self._load_config()

    def _load_config(self):
        config = configparser.ConfigParser()
        if not os.path.exists(self.config_path):
            logger.error(f"Config file not found: {self.config_path}")
            return
        config.read(self.config_path)
        try:
            ip = config['Battery_API']['IP']
            self.base_url = f"http://{ip}"
            self.poll_interval = int(config['Battery_API'].get('PollInterval', 2))
            logger.info(f"API endpoint: {self.base_url} | Poll interval: {self.poll_interval}s")
        except KeyError as e:
            logger.error(f"Missing config key: {e}")

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}{endpoint}"

    async def _get_json(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
        timeout: int = 10,
    ) -> dict | None:
        try:
            async with session.get(
                self._url(endpoint),
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status == 200:
                    return await response.json(content_type=None)
                logger.warning(f"GET {endpoint} → HTTP {response.status}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout on {endpoint}")
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection refused on {endpoint}: {e}")
        except aiohttp.ClientError as e:
            logger.error(f"Network error on {endpoint}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error on {endpoint}: {e}")
        return None

    async def fetch_static_info(
        self,
        session: aiohttp.ClientSession,
        max_retries: int = 5,
    ) -> bool:
        for attempt in range(1, max_retries + 1):
            logger.info(f"Fetching device info (attempt {attempt}/{max_retries})...")
            info_data = await self._get_json(session, ENDPOINT_INFO)
            config_data = await self._get_json(session, ENDPOINT_CONFIG)

            if info_data and config_data:
                self._parse_firmware_info(info_data)
                self._parse_battery_config(config_data)
                logger.info(f"Firmware : {self.firmware_info}")
                logger.info(f"Battery  : {self.battery_config}")
                return True

            if attempt < max_retries:
                wait = _BACKOFF_SEQUENCE[min(attempt - 1, len(_BACKOFF_SEQUENCE) - 1)]
                logger.warning(f"Device info unavailable. Retrying in {wait}s...")
                await asyncio.sleep(wait)

        logger.error("Could not fetch device info after all retries. Continuing with empty metadata.")
        return False

    def _parse_firmware_info(self, data: dict):
        mcs = data.get('MCS', {})
        # SCS may be named SCS_01, SCS_02, etc. — take the first one found.
        scs = next(
            (v for k, v in data.items() if k.startswith('SCS') and isinstance(v, dict)),
            {},
        )
        self.firmware_info = FirmwareInfo(
            mcs_core=mcs.get('core', ''),
            mcs_platform=mcs.get('platform', ''),
            mcs_system=mcs.get('system', ''),
            full_serial=mcs.get('full_serial', ''),
            serial=mcs.get('serial', 0),
            update_status=data.get('update_status', ''),
            scs_core=scs.get('core', ''),
            scs_serial=scs.get('full_serial', ''),
        )

    def _parse_battery_config(self, data: dict):
        bat = data.get('battery', {})
        sys_ = data.get('system', {})
        net = data.get('networkConfig', {})
        self.battery_config = BatteryConfig(
            battery_model=bat.get('battery_model', ''),
            strings_count=bat.get('stringsCount', 0),
            modules_per_string=bat.get('stringModulesCount', 0),
            nominal_capacity_ah=float(bat.get('stringNominalCapacity', 0)),
            inverter_model=sys_.get('converter_model', ''),
            ip_address=net.get('ipAddress', ''),
        )

    async def fetch_live_data(self, session: aiohttp.ClientSession):
        self._total_polls += 1
        data = await self._get_json(session, ENDPOINT_HOME, timeout=5)
        if data:
            await self.battery_data.update(**data)
            if not self._connected:
                logger.info("Battery API connection established.")
            self._connected = True
        else:
            if self._connected:
                logger.warning("Lost connection to Battery API.")
            self._connected = False
            self._error_count += 1

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def error_rate(self) -> float:
        if self._total_polls == 0:
            return 0.0
        return self._error_count / self._total_polls

    async def run_loop(self):
        self.running = True
        logger.info("Starting API polling loop...")
        async with aiohttp.ClientSession() as session:
            await self.fetch_static_info(session)
            self.static_info_ready.set()

            while self.running:
                await self.fetch_live_data(session)
                await asyncio.sleep(self.poll_interval)

        logger.info(
            f"API loop stopped. Polls: {self._total_polls} | "
            f"Errors: {self._error_count} ({self.error_rate:.1%})"
        )

    def stop(self):
        self.running = False
        logger.info("Stopping API polling loop.")
