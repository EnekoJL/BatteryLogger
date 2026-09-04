"""Shared fixtures: sample payloads + fake adapters implementing domain.ports
Protocols structurally (no inheritance needed — that's the point of Protocol)."""

import dataclasses
from datetime import datetime, timedelta

import pytest

from batterylogger.domain.calculations import EnergyStats
from batterylogger.domain.entities import BatteryReading, SessionSummary, apply_update
from batterylogger.domain.string_reading import StringReading, apply_string_update


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
def raw_string_payload():
    return {
        'id': 'S001',
        'current': 47.8,
        'voltage': 50.9,
        'soc': 99.0,
        'soh': 99.8,
        'power': 2433.0,
        'vcell': {'vcellMax': 3396, 'vcellMin': 3392, 'vcellAvg': 3393, 'internalResistance': 10.7},
        'dispersion': {'dispersionMax': 0, 'dispersionMin': 0, 'dispersionAvg': 1},
        'temperature': {'tempMax': 36.0, 'tempMin': 34.0, 'tempAmb': 33.9, 'tempPCB': 33.9},
        'event_mask': [0, 0, 0, 0, 0, 1],
    }


@pytest.fixture
def make_reading():
    def _make(**overrides) -> BatteryReading:
        return dataclasses.replace(BatteryReading(), **overrides)
    return _make


@pytest.fixture
def make_string_reading():
    def _make(**overrides) -> StringReading:
        return dataclasses.replace(StringReading(), **overrides)
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
    def __init__(self, static_info=None, live_readings=None, discovered_strings=None, string_readings=None):
        self._static_info = static_info
        self._live_readings = list(live_readings or [])
        self._discovered_strings = discovered_strings if discovered_strings is not None else []
        self._string_readings = string_readings or {}  # {string_id: raw_dict}
        self.static_calls = 0
        self.live_calls = 0
        self.discovered_strings_calls = 0
        self.string_reading_calls: list[int] = []

    async def fetch_static_info(self):
        self.static_calls += 1
        return self._static_info

    async def fetch_live_reading(self):
        self.live_calls += 1
        if self._live_readings:
            return self._live_readings.pop(0)
        return None

    async def fetch_discovered_strings(self):
        self.discovered_strings_calls += 1
        return self._discovered_strings

    async def fetch_string_reading(self, string_id: int):
        self.string_reading_calls.append(string_id)
        return self._string_readings.get(string_id)


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

    def configure(self, firmware, battery_config, discovered_strings=None):
        self.configured = (firmware, battery_config, discovered_strings or [])

    def write(self, reading, timestamp, string_readings=None):
        self.writes.append((reading, timestamp, string_readings or {}))

    def close(self, now) -> SessionSummary:
        self.closed_with = now
        return SessionSummary(filename='fake.csv', records_written=len(self.writes), duration_s=0)


class FakeStringStateRepository:
    def __init__(self):
        self._readings: dict[int, StringReading] = {}
        self.updates: list[tuple] = []

    async def update(self, string_id: int, patch: dict) -> StringReading:
        self.updates.append((string_id, patch))
        current = self._readings.get(string_id, StringReading())
        self._readings[string_id] = apply_string_update(current, patch)
        return self._readings[string_id]

    async def get_snapshot(self, string_id: int):
        return self._readings.get(string_id)

    async def get_all_snapshots(self) -> dict[int, StringReading]:
        return dict(self._readings)


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


@pytest.fixture
def fake_string_state_repo():
    return FakeStringStateRepository()
