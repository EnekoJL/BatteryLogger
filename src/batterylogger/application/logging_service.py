"""LoggingUseCase — orchestrates BMS polling, state updates, CSV persistence,
console status printing and alerting. Depends only on domain.ports
(Dependency Inversion) — no aiohttp/csv/configparser import here.
"""

import asyncio
import logging

from batterylogger.domain.config import AlertThresholds
from batterylogger.domain.entities import BatteryReading
from batterylogger.domain.ports import (
    AlertNotifierPort,
    BatteryApiPort,
    BatteryStateRepository,
    ClockPort,
    ReadingWriterPort,
    StringStateRepository,
)
from batterylogger.domain.value_objects import BatteryConfig, FirmwareInfo
from batterylogger.application.dto import DryRunResult, SessionReport

logger = logging.getLogger('logging_service')


class LoggingUseCase:
    def __init__(
        self,
        api: BatteryApiPort,
        state_repo: BatteryStateRepository,
        alerts: AlertNotifierPort,
        clock: ClockPort,
        poll_interval: int,
        alert_thresholds: AlertThresholds,
        writer: ReadingWriterPort | None = None,
        log_frequency: int = 60,
        status_interval: int = 10,
        string_state_repo: StringStateRepository | None = None,
        string_poll_interval: int = 30,
    ):
        self.api = api
        self.state_repo = state_repo
        self.alerts = alerts
        self.clock = clock
        self.poll_interval = poll_interval
        self.alert_thresholds = alert_thresholds
        self.writer = writer
        self.log_frequency = log_frequency
        self.status_interval = status_interval
        self.string_state_repo = string_state_repo
        self.string_poll_interval = string_poll_interval

        self.firmware_info = FirmwareInfo()
        self.battery_config = BatteryConfig()
        self.discovered_strings: list[int] = []
        self.static_info_ready = asyncio.Event()

        self._connected = False
        self._error_count = 0
        self._total_polls = 0

        self._shutdown_event: asyncio.Event | None = None
        self._tasks: list[asyncio.Task] = []
        self._start_time = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def error_rate(self) -> float:
        return self._error_count / self._total_polls if self._total_polls else 0.0

    # -- one-shot ----------------------------------------------------------

    async def dry_run(self) -> DryRunResult:
        result = await self.api.fetch_static_info()
        if result is None:
            return DryRunResult(ok=False, error="Could not reach the Battery API.")
        self.firmware_info, self.battery_config = result

        raw = await self.api.fetch_live_reading()
        reading = await self.state_repo.update(raw) if raw else None

        discovered = await self.api.fetch_discovered_strings() or []
        self.discovered_strings = discovered
        string_readings = {}
        if self.string_state_repo:
            for sid in discovered:
                raw_string = await self.api.fetch_string_reading(sid)
                if raw_string:
                    string_readings[sid] = await self.string_state_repo.update(sid, raw_string)

        return DryRunResult(
            ok=True,
            firmware=self.firmware_info,
            battery_config=self.battery_config,
            reading=reading,
            discovered_strings=discovered,
            string_readings=string_readings,
        )

    # -- long-running session ------------------------------------------------

    async def start(self) -> None:
        self._start_time = self.clock.now()
        self._shutdown_event = asyncio.Event()
        self._tasks = [asyncio.create_task(self._poll_api_loop(), name='api-poller')]
        if self.string_state_repo:
            self._tasks.append(asyncio.create_task(self._poll_strings_loop(), name='string-poller'))
        if self.writer:
            self._tasks.append(asyncio.create_task(self._write_csv_loop(), name='csv-writer'))
        self._tasks.append(asyncio.create_task(self._status_loop(), name='status-printer'))

    async def wait_for_static_info(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(asyncio.shield(self.static_info_ready.wait()), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        if self._shutdown_event is not None:
            self._shutdown_event.set()

    async def stop(self) -> SessionReport:
        self.request_shutdown()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        energy = await self.state_repo.get_energy_stats()
        csv_summary = self.writer.close(self.clock.now()) if self.writer else None
        duration_s = int((self.clock.now() - self._start_time).total_seconds())
        return SessionReport(
            duration_s=duration_s,
            total_polls=self._total_polls,
            error_rate=self.error_rate,
            energy=energy,
            csv_summary=csv_summary,
        )

    # -- internal loops ------------------------------------------------------

    async def _sleep_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def _poll_api_loop(self) -> None:
        result = await self.api.fetch_static_info()
        if result:
            self.firmware_info, self.battery_config = result
        discovered = await self.api.fetch_discovered_strings()
        if discovered is not None:
            self.discovered_strings = discovered
        self.static_info_ready.set()

        while not self._shutdown_event.is_set():
            self._total_polls += 1
            raw = await self.api.fetch_live_reading()
            if raw:
                await self.state_repo.update(raw)
                if not self._connected:
                    logger.info("Battery API connection established.")
                self._connected = True
            else:
                if self._connected:
                    logger.warning("Lost connection to Battery API.")
                self._connected = False
                self._error_count += 1
            await self._sleep_or_stop(self.poll_interval)

    async def _write_csv_loop(self) -> None:
        await self.static_info_ready.wait()  # ensures firmware/battery_config/discovered_strings are populated
        self.writer.configure(self.firmware_info, self.battery_config, self.discovered_strings)
        await self._sleep_or_stop(3)  # let a real reading arrive before the first row
        while not self._shutdown_event.is_set():
            snapshot = await self.state_repo.get_snapshot()
            string_snapshots = await self.string_state_repo.get_all_snapshots() if self.string_state_repo else {}
            self.writer.write(snapshot, self.clock.now(), string_snapshots)
            await self._sleep_or_stop(self.log_frequency)

    async def _poll_strings_loop(self) -> None:
        await self.static_info_ready.wait()  # discovered_strings populated by _poll_api_loop
        while not self._shutdown_event.is_set():
            for sid in self.discovered_strings:
                raw = await self.api.fetch_string_reading(sid)
                if raw:
                    await self.string_state_repo.update(sid, raw)
            await self._sleep_or_stop(self.string_poll_interval)

    async def _status_loop(self) -> None:
        while not self._shutdown_event.is_set():
            await self._sleep_or_stop(self.status_interval)
            if self._shutdown_event.is_set():
                break
            snapshot = await self.state_repo.get_snapshot()
            status_tag = "ONLINE " if self.is_connected else "OFFLINE"
            print(f"\n[{self.clock.now().strftime('%H:%M:%S')}] [{status_tag}] {snapshot}\n")
            self.check_alerts(snapshot)

    def check_alerts(self, snapshot: BatteryReading) -> None:
        """Split out from _status_loop so it's directly unit-testable."""
        if snapshot.voltage <= 0:
            return
        if snapshot.soc < self.alert_thresholds.soc_low:
            self.alerts.notify_low_soc(snapshot.soc, self.alert_thresholds.soc_low)
        if snapshot.temperature.tempMax > self.alert_thresholds.temp_high:
            self.alerts.notify_high_temp(snapshot.temperature.tempMax, self.alert_thresholds.temp_high)
