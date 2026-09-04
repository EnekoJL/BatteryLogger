import asyncio

from batterylogger.adapters.outbound.in_memory_string_state_repository import InMemoryStringStateRepository


async def test_update_merges_patch_for_a_string_id(raw_string_payload):
    repo = InMemoryStringStateRepository()
    reading = await repo.update(1, raw_string_payload)
    assert reading.id == 'S001'
    assert reading.soc == 99.0


async def test_get_snapshot_returns_none_for_unknown_string_id():
    repo = InMemoryStringStateRepository()
    assert await repo.get_snapshot(99) is None


async def test_string_ids_are_isolated_from_each_other():
    repo = InMemoryStringStateRepository()
    await repo.update(1, {'soc': 10.0})
    await repo.update(2, {'soc': 20.0})

    assert (await repo.get_snapshot(1)).soc == 10.0
    assert (await repo.get_snapshot(2)).soc == 20.0


async def test_get_all_snapshots_returns_every_known_string():
    repo = InMemoryStringStateRepository()
    await repo.update(1, {'soc': 10.0})
    await repo.update(4, {'soc': 40.0})

    snapshots = await repo.get_all_snapshots()
    assert set(snapshots.keys()) == {1, 4}
    assert snapshots[4].soc == 40.0


async def test_second_update_merges_onto_first_for_same_string():
    repo = InMemoryStringStateRepository()
    await repo.update(1, {'vcell': {'vcellMax': 3400}})
    reading = await repo.update(1, {'vcell': {'vcellMin': 3300}})

    assert reading.vcell.vcellMax == 3400  # preserved from first update
    assert reading.vcell.vcellMin == 3300


async def test_concurrent_updates_to_different_strings_are_serialized_safely():
    repo = InMemoryStringStateRepository()

    async def bump(sid, soc):
        await repo.update(sid, {'soc': soc})

    await asyncio.gather(*(bump(sid, float(sid * 10)) for sid in range(1, 7)))

    snapshots = await repo.get_all_snapshots()
    assert {sid: snapshots[sid].soc for sid in snapshots} == {sid: float(sid * 10) for sid in range(1, 7)}
