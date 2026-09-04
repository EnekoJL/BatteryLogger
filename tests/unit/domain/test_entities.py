from batterylogger.domain.entities import BatteryReading, apply_update


def test_apply_update_flat_field():
    reading = BatteryReading()
    updated = apply_update(reading, {'soc': 42.0, 'voltage': 51.5})
    assert updated.soc == 42.0
    assert updated.voltage == 51.5


def test_apply_update_nested_dataclass_merge():
    reading = BatteryReading()
    updated = apply_update(reading, {'vcell': {'vcellMax': 3400, 'vcellMin': 3300}})
    assert updated.vcell.vcellMax == 3400
    assert updated.vcell.vcellMin == 3300
    # untouched nested fields keep their defaults
    assert updated.vcell.vcellAvg == 0


def test_apply_update_unknown_key_ignored():
    reading = BatteryReading()
    updated = apply_update(reading, {'not_a_real_field': 123})
    assert not hasattr(updated, 'not_a_real_field')
    assert updated == reading


def test_apply_update_does_not_mutate_original():
    reading = BatteryReading(soc=10.0)
    apply_update(reading, {'soc': 99.0})
    assert reading.soc == 10.0  # original untouched — reading is frozen + pure merge


def test_apply_update_empty_patch_returns_same_values():
    reading = BatteryReading(soc=33.0)
    updated = apply_update(reading, {})
    assert updated == reading


def test_apply_update_partial_nested_patch_preserves_sibling_fields():
    reading = apply_update(BatteryReading(), {'vcell': {'vcellMax': 3400}})
    updated = apply_update(reading, {'vcell': {'vcellMin': 3300}})
    assert updated.vcell.vcellMax == 3400  # preserved from the first update
    assert updated.vcell.vcellMin == 3300
