"""aiohttp implementation of BatteryApiPort.

Config (IP, poll interval) is injected via ApiSettings — this adapter no
longer parses cfg.ini itself (that was the old api_controller.py's SRP
violation; parsing now lives solely in ini_config_repository.py).

Connection-health bookkeeping (is_connected / error_rate / poll counts)
moved to application.logging_service.LoggingUseCase — that's orchestration
concern, not "how do I talk HTTP to this device".
"""

import asyncio
import logging
from typing import Optional

import aiohttp

from batterylogger.domain.config import ApiSettings
from batterylogger.domain.ports import SleeperPort
from batterylogger.domain.value_objects import BatteryConfig, FirmwareInfo

logger = logging.getLogger(__name__)

ENDPOINT_HOME = "/api/bcs/home"
ENDPOINT_INFO = "/api/bcs/info"
ENDPOINT_CONFIG = "/api/bcs/config"

_BACKOFF_SEQUENCE = (2, 4, 8, 16, 30)


class AiohttpBmsClient:
    """Implements domain.ports.BatteryApiPort."""

    def __init__(self, settings: ApiSettings, sleeper: SleeperPort, max_retries: int = 5):
        self.base_url = settings.base_url
        self.poll_interval = settings.poll_interval
        self._sleeper = sleeper
        self._max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info(f"API endpoint: {self.base_url} | Poll interval: {self.poll_interval}s")

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

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
        return None

    async def fetch_static_info(self) -> Optional[tuple[FirmwareInfo, BatteryConfig]]:
        session = await self._ensure_session()
        for attempt in range(1, self._max_retries + 1):
            logger.info(f"Fetching device info (attempt {attempt}/{self._max_retries})...")
            info_data = await self._get_json(session, ENDPOINT_INFO)
            config_data = await self._get_json(session, ENDPOINT_CONFIG)

            if info_data and config_data:
                firmware = self._parse_firmware_info(info_data)
                battery_config = self._parse_battery_config(config_data)
                logger.info(f"Firmware : {firmware}")
                logger.info(f"Battery  : {battery_config}")
                return firmware, battery_config

            if attempt < self._max_retries:
                wait = _BACKOFF_SEQUENCE[min(attempt - 1, len(_BACKOFF_SEQUENCE) - 1)]
                logger.warning(f"Device info unavailable. Retrying in {wait}s...")
                await self._sleeper.sleep(wait)

        logger.error("Could not fetch device info after all retries. Continuing with empty metadata.")
        return None

    async def fetch_live_reading(self) -> Optional[dict]:
        session = await self._ensure_session()
        return await self._get_json(session, ENDPOINT_HOME, timeout=5)

    @staticmethod
    def _parse_firmware_info(data: dict) -> FirmwareInfo:
        mcs = data.get('MCS', {})
        # SCS may be named SCS_01, SCS_02, etc. — take the first one found.
        scs = next(
            (v for k, v in data.items() if k.startswith('SCS') and isinstance(v, dict)),
            {},
        )
        return FirmwareInfo(
            mcs_core=mcs.get('core', ''),
            mcs_platform=mcs.get('platform', ''),
            mcs_system=mcs.get('system', ''),
            full_serial=mcs.get('full_serial', ''),
            serial=mcs.get('serial', 0),
            update_status=data.get('update_status', ''),
            scs_core=scs.get('core', ''),
            scs_serial=scs.get('full_serial', ''),
        )

    @staticmethod
    def _parse_battery_config(data: dict) -> BatteryConfig:
        bat = data.get('battery', {})
        sys_ = data.get('system', {})
        net = data.get('networkConfig', {})
        return BatteryConfig(
            battery_model=bat.get('battery_model', ''),
            strings_count=bat.get('stringsCount', 0),
            modules_per_string=bat.get('stringModulesCount', 0),
            nominal_capacity_ah=float(bat.get('stringNominalCapacity', 0)),
            inverter_model=sys_.get('converter_model', ''),
            ip_address=net.get('ipAddress', ''),
        )
