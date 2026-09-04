import asyncio

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


def _backoff_calls(sleeper: FakeSleeper) -> list[float]:
    """Filters out the sub-second per-request throttle sleeps (see
    AiohttpBmsClient._throttle), leaving only the retry-backoff waits."""
    return [c for c in sleeper.calls if c >= 1]


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
    assert _backoff_calls(sleeper) == [2]  # first backoff step, no real wait


async def test_fetch_static_info_exhausts_retries_returns_none():
    client, sleeper = await make_client(max_retries=3)
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/info', status=500, repeat=True)
        m.get(f'{BASE}/api/bcs/config', status=500, repeat=True)
        result = await client.fetch_static_info()
    await client.close()

    assert result is None
    assert _backoff_calls(sleeper) == [2, 4]  # backoff before attempts 2 and 3, none after the last


async def test_fetch_discovered_strings_parses_non_contiguous_ids():
    client, _ = await make_client()
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/string', payload={'stringInfo': {'discovered': [1, 2, 4]}})
        discovered = await client.fetch_discovered_strings()
    await client.close()
    assert discovered == [1, 2, 4]


async def test_fetch_discovered_strings_http_error_returns_none():
    client, _ = await make_client()
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/string', status=500)
        discovered = await client.fetch_discovered_strings()
    await client.close()
    assert discovered is None


async def test_fetch_string_reading_zero_pads_url_and_extracts_battery_info(raw_string_payload):
    client, _ = await make_client()
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/battery/S04', payload={'batteryInfo': raw_string_payload})
        data = await client.fetch_string_reading(4)
    await client.close()
    assert data == raw_string_payload


async def test_fetch_string_reading_double_digit_id():
    client, _ = await make_client()
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/battery/S12', payload={'batteryInfo': {'id': 'S012'}})
        data = await client.fetch_string_reading(12)
    await client.close()
    assert data == {'id': 'S012'}


async def test_fetch_string_reading_endpoint_unreachable_returns_none():
    client, _ = await make_client()
    with aioresponses() as m:
        m.get(f'{BASE}/api/bcs/battery/S01', status=500)
        data = await client.fetch_string_reading(1)
    await client.close()
    assert data is None


class TestRequestThrottling:
    """The BMS itself rejects (HTTP 429) any two requests under 100ms apart
    — confirmed by the device owner. Every call funnels through _get_json's
    _throttle(), so this covers pack polling, string polling, and the two
    back-to-back calls inside fetch_static_info alike."""

    async def test_first_request_is_not_throttled(self):
        client, sleeper = await make_client()
        with aioresponses() as m:
            m.get(f'{BASE}/api/bcs/home', payload={})
            await client.fetch_live_reading()
        await client.close()
        assert sleeper.calls == []

    async def test_second_immediate_request_is_throttled_by_roughly_min_interval(self):
        client, sleeper = await make_client()
        with aioresponses() as m:
            m.get(f'{BASE}/api/bcs/home', payload={})
            m.get(f'{BASE}/api/bcs/home', payload={})
            await client.fetch_live_reading()
            await client.fetch_live_reading()
        await client.close()

        assert len(sleeper.calls) == 1
        # essentially no real time passed between the two calls in this test,
        # so the throttle should ask for close to the full min interval
        assert 0.09 <= sleeper.calls[0] <= client._min_request_interval

    async def test_static_infos_two_calls_are_throttled_against_each_other(self, raw_info_payload, raw_config_payload):
        # this is the exact sequence that produced spurious 429s in the wild:
        # /info immediately followed by /config with zero gap.
        client, sleeper = await make_client()
        with aioresponses() as m:
            m.get(f'{BASE}/api/bcs/info', payload=raw_info_payload)
            m.get(f'{BASE}/api/bcs/config', payload=raw_config_payload)
            result = await client.fetch_static_info()
        await client.close()

        assert result is not None
        assert len(sleeper.calls) == 1  # throttle between the info call and the config call

    async def test_concurrent_callers_are_serialized_not_raced(self):
        # pack poller + string poller could both want to fire "at once" —
        # the throttle lock must queue them, not let both slip through.
        client, sleeper = await make_client()
        with aioresponses() as m:
            for _ in range(4):
                m.get(f'{BASE}/api/bcs/home', payload={})
            await asyncio.gather(*(client.fetch_live_reading() for _ in range(4)))
        await client.close()

        assert len(sleeper.calls) == 3  # first request free, other 3 throttled in turn
