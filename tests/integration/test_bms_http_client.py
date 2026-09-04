from aioresponses import aioresponses

from batterylogger.adapters.outbound.bms_http_client import AiohttpBmsClient
from batterylogger.domain.config import ApiSettings

BASE = 'http://192.168.55.193'


class FakeSleeper:
    def __init__(self):
        self.calls: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)  # no real wait — instant


async def make_client(max_retries: int = 5) -> tuple[AiohttpBmsClient, FakeSleeper]:
    sleeper = FakeSleeper()
    client = AiohttpBmsClient(ApiSettings(base_url=BASE, poll_interval=2), sleeper, max_retries=max_retries)
    return client, sleeper


async def test_fetch_live_reading_success():
    client, _ = await make_client()
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/home', payload={'soc': 50.0, 'voltage': 51.0})
        data = await client.fetch_live_reading()
    await client.close()
    assert data == {'soc': 50.0, 'voltage': 51.0}


async def test_fetch_live_reading_http_error_returns_none():
    client, _ = await make_client()
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/home', status=500)
        data = await client.fetch_live_reading()
    await client.close()
    assert data is None


async def test_fetch_static_info_parses_firmware_and_config(raw_info_payload, raw_config_payload):
    client, _ = await make_client()
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/info', payload=raw_info_payload)
        m.get(f'{BASE}/api/bcs/config', payload=raw_config_payload)
        result = await client.fetch_static_info()
    await client.close()

    assert result is not None
    firmware, battery_config = result
    assert firmware.mcs_core == 'v1.16.10'
    assert firmware.scs_core == 'v1.2.0'
    assert battery_config.battery_model == 'E_BICK_LV_280'
    assert battery_config.nominal_capacity_ah == 280.0


async def test_fetch_static_info_retries_then_succeeds(raw_info_payload, raw_config_payload):
    client, sleeper = await make_client(max_retries=3)
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/info', status=500)  # attempt 1 fails
        m.get(f'{BASE}/api/bcs/config', payload=raw_config_payload)
        m.get(f'{BASE}/api/bcs/info', payload=raw_info_payload)  # attempt 2 succeeds
        m.get(f'{BASE}/api/bcs/config', payload=raw_config_payload)
        result = await client.fetch_static_info()
    await client.close()

    assert result is not None
    assert sleeper.calls == [2]  # first backoff step, no real wait


async def test_fetch_static_info_exhausts_retries_returns_none():
    client, sleeper = await make_client(max_retries=3)
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/info', status=500, repeat=True)
        m.get(f'{BASE}/api/bcs/config', status=500, repeat=True)
        result = await client.fetch_static_info()
    await client.close()

    assert result is None
    assert sleeper.calls == [2, 4]  # backoff before attempts 2 and 3, none after the last
