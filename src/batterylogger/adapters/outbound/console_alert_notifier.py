"""Console/log-based alerting. Swappable later for email/Slack/etc. without
touching LoggingUseCase (Open/Closed principle)."""

import logging


class ConsoleAlertNotifier:
    """Implements domain.ports.AlertNotifierPort."""

    def __init__(self):
        self._logger = logging.getLogger('alerts')

    def notify_low_soc(self, soc: float, threshold: float) -> None:
        self._logger.warning(f"LOW SOC ALERT: {soc:.1f}% (threshold {threshold}%)")

    def notify_high_temp(self, temp: float, threshold: float) -> None:
        self._logger.warning(f"HIGH TEMP ALERT: {temp:.1f}°C (threshold {threshold}°C)")
