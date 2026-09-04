import pandas as pd

from batterylogger.domain.string_reading import DispersionData, StringReading, apply_string_update, detect_string_ids


def test_dispersion_data_defaults():
    d = DispersionData()
    assert d.dispersionMax == 0.0
    assert d.dispersionMaxMcl == 0
    assert d.dispersionAvg == 0.0


def test_string_reading_default_event_mask_has_six_zeros():
    # Fixed length so a default instance flattens to a stable header —
    # see CsvReadingWriter.configure().
    assert StringReading().event_mask == [0, 0, 0, 0, 0, 0]


def test_apply_string_update_flat_field():
    reading = apply_string_update(StringReading(), {'soc': 99.0, 'voltage': 50.9})
    assert reading.soc == 99.0
    assert reading.voltage == 50.9


def test_apply_string_update_nested_dataclass_merge():
    reading = apply_string_update(StringReading(), {
        'vcell': {'vcellMax': 3396, 'vcellMin': 3392},
        'dispersion': {'dispersionAvg': 1},
    })
    assert reading.vcell.vcellMax == 3396
    assert reading.vcell.vcellMin == 3392
    assert reading.dispersion.dispersionAvg == 1


def test_apply_string_update_event_mask_list():
    reading = apply_string_update(StringReading(), {'event_mask': [0, 0, 0, 0, 0, 1]})
    assert reading.event_mask == [0, 0, 0, 0, 0, 1]


def test_apply_string_update_unknown_key_ignored():
    reading = apply_string_update(StringReading(), {'not_a_real_field': 1})
    assert reading == StringReading()


def test_apply_string_update_does_not_mutate_original():
    reading = StringReading(soc=10.0)
    apply_string_update(reading, {'soc': 99.0})
    assert reading.soc == 10.0


def test_apply_string_update_from_real_payload_shape(raw_string_payload):
    reading = apply_string_update(StringReading(), raw_string_payload)
    assert reading.id == 'S001'
    assert reading.soc == 99.0
    assert reading.vcell.vcellMax == 3396
    assert reading.dispersion.dispersionAvg == 1
    assert reading.event_mask == [0, 0, 0, 0, 0, 1]


class TestDetectStringIds:
    def test_no_string_columns_returns_empty(self):
        df = pd.DataFrame({'soc': [1, 2], 'voltage': [50, 51]})
        assert detect_string_ids(df) == []

    def test_finds_contiguous_ids(self):
        df = pd.DataFrame({'string1_soc': [1], 'string2_soc': [2], 'voltage': [50]})
        assert detect_string_ids(df) == [1, 2]

    def test_finds_non_contiguous_ids_sorted(self):
        df = pd.DataFrame({'string4_soc': [1], 'string1_soc': [2]})
        assert detect_string_ids(df) == [1, 4]

    def test_ignores_other_string_prefixed_columns(self):
        # only the `_soc` marker column should be used to detect presence
        df = pd.DataFrame({'string1_voltage': [50], 'string1_soc': [80]})
        assert detect_string_ids(df) == [1]
