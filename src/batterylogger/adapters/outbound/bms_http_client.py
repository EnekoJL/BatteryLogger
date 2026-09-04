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
import time
from typing import Optional

import aiohttp

from batterylogger.domain.config import ApiSettings
from batterylogger.domain.ports import SleeperPort
from batterylogger.domain.value_objects import BatteryConfig, FirmwareInfo

logger = logging.getLogger(__name__)

ENDPOINT_HOME = "/api/bcs/home"
ENDPOINT_INFO = "/api/bcs/info"
ENDPOINT_CONFIG = "/api/bcs/config"
ENDPOINT_STRING = "/api/bcs/string"

# The BMS itself rejects (HTTP 429) any two requests received under 100ms
# apart — confirmed by the device owner, not a tunable/config choice. Every
# call funnels through _get_json, so throttling there covers every endpoint
# and every caller (pack poll, string polls, static info's two calls back
# to back, dry-run) without each call site needing its own pacing logic.
MIN_REQUEST_INTERVAL_S = 0.11  # 100ms + small safety margin


def _string_battery_endpoint(string_id: int) -> str:
    return f"/api/bcs/battery/S{string_id:02d}"

_BACKOFF_SEQUENCE = (2, 4, 8, 16, 30)


class AiohttpBmsClient:
    """Implements domain.ports.BatteryApiPort."""

    def __init__(
        self,
        settings: ApiSettings,
        sleeper: SleeperPort,
        max_retries: int = 5,
        min_request_interval: float = MIN_REQUEST_INTERVAL_S,
    ):
        self.base_url = settings.base_url
        self.poll_interval = settings.poll_interval
        self._sleeper = sleeper
        self._max_retries = max_retries
        self._min_request_interval = min_request_interval
        self._session: Optional[aiohttp.ClientSession] = None
        self._throttle_lock = asyncio.Lock()
        self._last_request_at: Optional[float] = None
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
        # Holds the lock for the FULL request (throttle wait + the actual GET),
        # not just the pre-request check — and measures the gap from when the
        # previous response actually finished, not when it was sent. A real
        # network round-trip takes non-zero time; spacing only request *start*
        # times can still land two requests close together at the device if
        # the first one was slow to answer. This fully serializes access:
        # no two requests are ever in flight at once, and each one starts
        # >= min_request_interval after the previous one's response arrived.
        async with self._throttle_lock:
            if self._last_request_at is not None:
                elapsed = time.monotonic() - self._last_request_at
                remaining = self._min_request_interval - elapsed
                if remaining > 0:
                    await self._sleeper.sleep(remaining)
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
            finally:
                self._last_request_at = time.monotonic()
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
        # /api/bcs/home wraps its payload in {"batteryInfo": {...}} — same
        # shape as the per-string endpoint. Falls back to the raw dict if
        # ever unwrapped, matching the old code's defensive handling.
        session = await self._ensure_session()
        data = await self._get_json(session, ENDPOINT_HOME, timeout=5)
        if data is None:
            return None
        return data.get('batteryInfo', data)

    async def fetch_discovered_strings(self) -> Optional[list[int]]:
        session = await self._ensure_session()
        data = await self._get_json(session, ENDPOINT_STRING, timeout=5)
        if data is None:
            return None
        return data.get('stringInfo', {}).get('discovered', [])

    async def fetch_string_reading(self, string_id: int) -> Optional[dict]:
        session = await self._ensure_session()
        data = await self._get_json(session, _string_battery_endpoint(string_id), timeout=5)
        if data is None:
            return None
        return data.get('batteryInfo')

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
