"""Shared fixtures: sample payloads + fake adapters implementing domain.ports
Protocols structurally (no inheritance needed — that's the point of Protocol)."""

import dataclasses
from datetime import datetime, timedelta

import pytest

from batterylogger.domain.calculations import EnergyStats
from batterylogger.domain.entities import BatteryReading, SessionSummary, apply_update


# ---------------------------------------------------------------------------
# Raw BMS payload fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_home_payload():
    return {
        'id': 'BAT1',
        'current': -10.0,
        'voltage': 52.0,
        'soc': 55.0,
        'power': -520.0,
        'vcell': {'vcellMax': 3400, 'vcellMin': 3350, 'internalResistance': 1.5},
        'temperature': {'tempMax': 30.0, 'tempMin': 25.0},
    }


@pytest.fixture
def raw_info_payload():
    return {
        'MCS': {'core': 'v1.16.10', 'full_serial': 'SN123'},
        'SCS_01': {'core': 'v1.2.0', 'full_serial': 'SN456'},
        'update_status': 'idle',
    }


@pytest.fixture
def raw_config_payload():
    return {
        'battery': {
            'battery_model': 'E_BICK_LV_280',
            'stringsCount': 1,
            'stringModulesCount': 1,
            'stringNominalCapacity': 280,
        },
        'system': {'converter_model': 'INV-X'},
        'networkConfig': {'ipAddress': '192.168.55.193'},
    }


@pytest.fixture
def make_reading():
    def _make(**overrides) -> BatteryReading:
        return dataclasses.replace(BatteryReading(), **overrides)
    return _make


@pytest.fixture
def sample_log_csv_path():
    import os
    return os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_log.csv')


# ---------------------------------------------------------------------------
# Fake adapters (structurally satisfy domain.ports Protocols)
# ---------------------------------------------------------------------------

class FakeClock:
    def __init__(self, start: datetime | None = None):
        self._now = start or datetime(2026, 1, 1, 0, 0, 0)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


class FakeBatteryApi:
    def __init__(self, static_info=None, live_readings=None):
        self._static_info = static_info
        self._live_readings = list(live_readings or [])
        self.static_calls = 0
        self.live_calls = 0

    async def fetch_static_info(self):
        self.static_calls += 1
        return self._static_info

    async def fetch_live_reading(self):
        self.live_calls += 1
        if self._live_readings:
            return self._live_readings.pop(0)
        return None


class FakeStateRepository:
    def __init__(self):
        self._reading = BatteryReading()
        self._energy = EnergyStats()
        self.updates: list[dict] = []

    async def update(self, patch: dict) -> BatteryReading:
        self.updates.append(patch)
        self._reading = apply_update(self._reading, patch)
        return self._reading

    async def get_snapshot(self) -> BatteryReading:
        return self._reading

    async def get_energy_stats(self) -> EnergyStats:
        return self._energy


class FakeWriter:
    def __init__(self):
        self.configured = None
        self.writes: list[tuple] = []
        self.closed_with = None

    def configure(self, firmware, battery_config):
        self.configured = (firmware, battery_config)

    def write(self, reading, timestamp):
        self.writes.append((reading, timestamp))

    def close(self, now) -> SessionSummary:
        self.closed_with = now
        return SessionSummary(filename='fake.csv', records_written=len(self.writes), duration_s=0)


class FakeAlertNotifier:
    def __init__(self):
        self.low_soc_calls: list[tuple] = []
        self.high_temp_calls: list[tuple] = []

    def notify_low_soc(self, soc, threshold):
        self.low_soc_calls.append((soc, threshold))

    def notify_high_temp(self, temp, threshold):
        self.high_temp_calls.append((temp, threshold))


@pytest.fixture
def fake_clock():
    return FakeClock()


@pytest.fixture
def fake_alerts():
    return FakeAlertNotifier()


@pytest.fixture
def fake_writer():
    return FakeWriter()


@pytest.fixture
def fake_state_repo():
    return FakeStateRepository()
