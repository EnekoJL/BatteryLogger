"""Composition root — the ONLY module that imports both port interfaces
and concrete adapter classes. Everything else (application/, domain/,
adapters/inbound/) only ever sees the ports.
"""

import dataclasses
from dataclasses import dataclass
from typing import Optional

from batterylogger.adapters.outbound.bms_http_client import AiohttpBmsClient
from batterylogger.adapters.outbound.console_alert_notifier import ConsoleAlertNotifier
from batterylogger.adapters.outbound.csv_reading_parser import CsvReadingParser
from batterylogger.adapters.outbound.csv_reading_writer import CsvReadingWriter
from batterylogger.adapters.outbound.ini_config_repository import IniConfigRepository
from batterylogger.adapters.outbound.in_memory_state_repository import InMemoryStateRepository
from batterylogger.adapters.outbound.system_clock import AsyncSleeper, SystemClock
from batterylogger.application.analysis_service import AnalysisUseCase
from batterylogger.application.logging_service import LoggingUseCase
from batterylogger.domain.config import BatteryTopology


@dataclass
class LoggerContainer:
    use_case: LoggingUseCase
    api_client: AiohttpBmsClient
    topology: BatteryTopology


def build_logger_container(
    config_path: str,
    no_csv: bool = False,
    poll_interval_override: Optional[int] = None,
    log_freq_override: Optional[int] = None,
    status_interval: int = 10,
) -> LoggerContainer:
    config_repo = IniConfigRepository(config_path)

    api_settings = config_repo.load_api_settings()
    if poll_interval_override:
        api_settings = dataclasses.replace(api_settings, poll_interval=poll_interval_override)

    topology = config_repo.load_battery_topology()
    alert_thresholds = config_repo.load_alert_thresholds()

    logger_settings = config_repo.load_logger_settings()
    if log_freq_override:
        logger_settings = dataclasses.replace(logger_settings, log_frequency=log_freq_override)

    clock = SystemClock()
    sleeper = AsyncSleeper()
    api_client = AiohttpBmsClient(api_settings, sleeper)
    state_repo = InMemoryStateRepository(topology, clock)
    alerts = ConsoleAlertNotifier()

    writer = None
    if not no_csv:
        writer = CsvReadingWriter(rotate_daily=logger_settings.rotate_daily, config_path=config_path)

    use_case = LoggingUseCase(
        api=api_client,
        state_repo=state_repo,
        alerts=alerts,
        clock=clock,
        poll_interval=api_settings.poll_interval,
        alert_thresholds=alert_thresholds,
        writer=writer,
        log_frequency=logger_settings.log_frequency,
        status_interval=status_interval,
    )

    return LoggerContainer(use_case=use_case, api_client=api_client, topology=topology)


def build_analysis_use_case() -> AnalysisUseCase:
    return AnalysisUseCase(parser=CsvReadingParser())
