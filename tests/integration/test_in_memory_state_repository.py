import asyncio

from batterylogger.adapters.outbound.in_memory_state_repository import InMemoryStateRepository
from batterylogger.domain.config import BatteryTopology
from tests.conftest import FakeClock


async def test_update_merges_patch_and_computes_derived_vcell():
    repo = InMemoryStateRepository(BatteryTopology(num_cells=15, num_modules=1), FakeClock())

    reading = await repo.update({
        'current': -20.0,
        'vcell': {'vcellMin': 3300, 'vcellMax': 3400, 'internalResistance': 15.0},
    })

    assert reading.vcell.cellInternalResistance == 1.0  # 15.0 / (15*1)
    assert reading.vcell.corrected_vcell == 3300 + 20.0 * 1.0  # discharge branch


async def test_get_snapshot_reflects_latest_update():
    repo = InMemoryStateRepository(BatteryTopology(), FakeClock())
    await repo.update({'soc': 42.0})
    snapshot = await repo.get_snapshot()
    assert snapshot.soc == 42.0


async def test_energy_accumulates_between_updates_using_clock():
    clock = FakeClock()
    repo = InMemoryStateRepository(BatteryTopology(), clock)

    await repo.update({'power': 100.0})  # first update: no dt yet, no accumulation
    clock.advance(3600)  # 1 hour later
    await repo.update({'power': 100.0})

    energy = await repo.get_energy_stats()
    assert energy.energy_ch_wh == 100.0  # 100W for 1h = 100Wh


async def test_concurrent_updates_are_serialized_by_the_lock():
    repo = InMemoryStateRepository(BatteryTopology(), FakeClock())

    async def bump(n):
        await repo.update({'soc': float(n)})

    await asyncio.gather(*(bump(n) for n in range(20)))

    snapshot = await repo.get_snapshot()
    assert snapshot.soc in [float(n) for n in range(20)]  # no torn/corrupted state
