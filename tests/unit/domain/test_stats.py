import pandas as pd

from batterylogger.domain.stats import compute_session_stats


def _full_df():
    return pd.DataFrame({
        'Timestamp': pd.date_range('2026-01-01 00:00:00', periods=4, freq='1h'),
        'soc': [80.0, 70.0, 60.0, 50.0],
        'current': [10.0, -5.0, 15.0, -20.0],
        'temperature_tempMax': [25.0, 26.0, 30.0, 28.0],
        'temperature_tempMin': [20.0, 21.0, 22.0, 20.0],
        'vcell_vcellMax': [3400, 3410, 3420, 3430],
        'vcell_vcellMin': [3300, 3305, 3310, 3315],
        'vcell_internalResistance': [1.0, 1.2, 0.9, 1.5],
    })


def test_record_count_and_duration():
    stats = compute_session_stats(_full_df())
    assert stats.record_count == 4
    assert stats.duration_str == '03:00:00'


def test_soc_range_and_biggest_jump():
    stats = compute_session_stats(_full_df())
    assert stats.soc_min == 50.0
    assert stats.soc_max == 80.0
    assert stats.biggest_soc_jump_pct == 10.0


def test_peak_charge_and_discharge():
    stats = compute_session_stats(_full_df())
    assert stats.peak_charge_a == 15.0
    assert stats.peak_discharge_a == 20.0


def test_cell_voltage_and_ir_stats():
    stats = compute_session_stats(_full_df())
    assert stats.max_cell_v == 3430
    assert stats.min_cell_v == 3300
    assert stats.max_cell_spread_mv == 115  # row-wise (max-min), largest is row 4: 3430-3315
    assert stats.max_pack_ir == 1.5


def test_temperature_stats():
    stats = compute_session_stats(_full_df())
    assert stats.max_temp == 30.0
    assert stats.max_temp_spread == 8.0  # max(tempMax - tempMin) = 30 - 22


def test_missing_columns_yield_none_fields():
    df = pd.DataFrame({'soc': [10, 20]})
    stats = compute_session_stats(df)
    assert stats.record_count == 2
    assert stats.duration_str is None
    assert stats.max_temp is None
    assert stats.peak_charge_a is None
    assert stats.max_cell_v is None


def test_no_negative_current_means_no_peak_discharge():
    df = _full_df().assign(current=[1.0, 2.0, 3.0, 0.5])
    stats = compute_session_stats(df)
    assert stats.peak_charge_a == 3.0
    assert stats.peak_discharge_a is None
