import asyncio

import pytest

from batterylogger.application.logging_service import LoggingUseCase
from batterylogger.domain.config import AlertThresholds
from batterylogger.domain.value_objects import BatteryConfig, FirmwareInfo
from tests.conftest import (
    FakeAlertNotifier,
    FakeBatteryApi,
    FakeClock,
    FakeStateRepository,
    FakeStringStateRepository,
    FakeWriter,
)


def make_use_case(**overrides):
    defaults = dict(
        api=FakeBatteryApi(),
        state_repo=FakeStateRepository(),
        alerts=FakeAlertNotifier(),
        clock=FakeClock(),
        poll_interval=1,
        alert_thresholds=AlertThresholds(soc_low=20.0, temp_high=40.0),
        string_state_repo=FakeStringStateRepository(),
        string_poll_interval=1,
    )
    defaults.update(overrides)
    return LoggingUseCase(**defaults)


class TestDryRun:
    async def test_returns_ok_false_when_static_info_unavailable(self):
        use_case = make_use_case(api=FakeBatteryApi(static_info=None))
        result = await use_case.dry_run()
        assert result.ok is False
        assert result.error

    async def test_returns_reading_when_data_available(self, raw_home_payload):
        static_info = (FirmwareInfo(mcs_core='v1'), BatteryConfig(battery_model='E_BICK_LV_280'))
        api = FakeBatteryApi(static_info=static_info, live_readings=[raw_home_payload])
        use_case = make_use_case(api=api)
        result = await use_case.dry_run()
        assert result.ok is True
        assert result.firmware.mcs_core == 'v1'
        assert result.reading is not None
        assert result.reading.soc == 55.0

    async def test_ok_true_with_no_reading_when_live_fetch_fails(self):
        static_info = (FirmwareInfo(), BatteryConfig())
        api = FakeBatteryApi(static_info=static_info, live_readings=[])
        use_case = make_use_case(api=api)
        result = await use_case.dry_run()
        assert result.ok is True
        assert result.reading is None

    async def test_includes_discovered_strings_and_readings(self, raw_string_payload):
        static_info = (FirmwareInfo(), BatteryConfig())
        api = FakeBatteryApi(
            static_info=static_info,
            discovered_strings=[1, 4],
            string_readings={1: raw_string_payload, 4: raw_string_payload},
        )
        use_case = make_use_case(api=api)
        result = await use_case.dry_run()
        assert result.discovered_strings == [1, 4]
        assert set(result.string_readings.keys()) == {1, 4}
        assert result.string_readings[1].soc == 99.0

    async def test_missing_string_reading_is_skipped(self):
        static_info = (FirmwareInfo(), BatteryConfig())
        api = FakeBatteryApi(static_info=static_info, discovered_strings=[1, 2], string_readings={1: {'soc': 50.0}})
        use_case = make_use_case(api=api)
        result = await use_case.dry_run()
        assert set(result.string_readings.keys()) == {1}  # string 2 never responded


class TestCheckAlerts:
    def test_low_soc_triggers_notification(self, make_reading):
        alerts = FakeAlertNotifier()
        use_case = make_use_case(alerts=alerts, alert_thresholds=AlertThresholds(soc_low=20.0, temp_high=40.0))
        reading = make_reading(voltage=50.0, soc=10.0)
        use_case.check_alerts(reading)
        assert alerts.low_soc_calls == [(10.0, 20.0)]
        assert alerts.high_temp_calls == []

    def test_high_temp_triggers_notification(self, make_reading):
        import dataclasses
        from batterylogger.domain.entities import TemperatureData

        alerts = FakeAlertNotifier()
        use_case = make_use_case(alerts=alerts, alert_thresholds=AlertThresholds(soc_low=20.0, temp_high=40.0))
        reading = make_reading(voltage=50.0, soc=80.0, temperature=TemperatureData(tempMax=55.0))
        use_case.check_alerts(reading)
        assert alerts.high_temp_calls == [(55.0, 40.0)]
        assert alerts.low_soc_calls == []

    def test_no_alert_when_within_thresholds(self, make_reading):
        alerts = FakeAlertNotifier()
        use_case = make_use_case(alerts=alerts)
        reading = make_reading(voltage=50.0, soc=80.0)
        use_case.check_alerts(reading)
        assert alerts.low_soc_calls == []
        assert alerts.high_temp_calls == []

    def test_no_alert_when_voltage_zero_no_live_data_yet(self, make_reading):
        alerts = FakeAlertNotifier()
        use_case = make_use_case(alerts=alerts)
        reading = make_reading(voltage=0.0, soc=1.0)  # would trip low-soc if voltage weren't gated
        use_case.check_alerts(reading)
        assert alerts.low_soc_calls == []


class TestSessionLifecycle:
    async def test_start_then_stop_produces_report_and_polls_api(self):
        api = FakeBatteryApi(static_info=(FirmwareInfo(), BatteryConfig()), live_readings=[])
        use_case = make_use_case(api=api, poll_interval=100)  # long interval so we control timing via stop()
        await use_case.start()
        await asyncio.sleep(0.05)  # let the tasks get one iteration in
        report = await use_case.stop()

        assert api.static_calls == 1
        assert api.live_calls >= 1
        assert report.total_polls >= 1
        assert report.duration_s >= 0

    async def test_writer_is_configured_and_closed_when_present(self):
        writer = FakeWriter()
        api = FakeBatteryApi(static_info=(FirmwareInfo(mcs_core='fw1'), BatteryConfig(battery_model='X')))
        use_case = make_use_case(api=api, writer=writer, poll_interval=100, log_frequency=100)
        await use_case.start()
        await asyncio.sleep(0.05)
        report = await use_case.stop()

        assert writer.configured == (FirmwareInfo(mcs_core='fw1'), BatteryConfig(battery_model='X'), [])
        assert writer.closed_with is not None
        assert report.csv_summary is not None

    async def test_string_poller_updates_string_state_repo(self, raw_string_payload):
        api = FakeBatteryApi(
            static_info=(FirmwareInfo(), BatteryConfig()),
            discovered_strings=[1, 2],
            string_readings={1: raw_string_payload, 2: raw_string_payload},
        )
        string_repo = FakeStringStateRepository()
        use_case = make_use_case(api=api, string_state_repo=string_repo, poll_interval=100, string_poll_interval=100)
        await use_case.start()
        await asyncio.sleep(0.05)
        await use_case.stop()

        assert sorted(api.string_reading_calls) == [1, 2]
        snapshots = await string_repo.get_all_snapshots()
        assert set(snapshots.keys()) == {1, 2}
        assert snapshots[1].soc == 99.0

    async def test_writer_receives_discovered_strings_on_configure(self):
        # _write_csv_loop has a fixed 3s warm-up before its first write() call
        # (lets a real reading arrive), so this only checks configure() wiring
        # — write()-with-string-data content is covered at the CsvReadingWriter
        # adapter level (tests/integration/test_csv_reading_writer.py).
        writer = FakeWriter()
        api = FakeBatteryApi(static_info=(FirmwareInfo(), BatteryConfig()), discovered_strings=[1])
        use_case = make_use_case(api=api, writer=writer, poll_interval=100, log_frequency=100, string_poll_interval=100)
        await use_case.start()
        await asyncio.sleep(0.05)
        await use_case.stop()

        assert writer.configured == (FirmwareInfo(), BatteryConfig(), [1])

    async def test_wait_for_static_info_times_out_when_api_never_responds(self):
        class HangingApi(FakeBatteryApi):
            async def fetch_static_info(self):
                await asyncio.sleep(10)
                return None

        use_case = make_use_case(api=HangingApi())
        await use_case.start()
        got_info = await use_case.wait_for_static_info(timeout=0.05)
        assert got_info is False
        await use_case.stop()
