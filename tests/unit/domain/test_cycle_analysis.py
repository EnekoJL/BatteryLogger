import pandas as pd
import pytest

from batterylogger.domain.cycle_analysis import detect_cycles


def test_detect_cycles_returns_empty_when_required_columns_missing():
    df = pd.DataFrame({'soc': [50, 60], 'Timestamp': ['2026-01-01', '2026-01-02']})
    assert detect_cycles(df) == []


def test_detect_cycles_ignores_shallow_segments():
    # ΔSOC < 50 everywhere — should yield no cycles
    df = pd.DataFrame({
        'Timestamp': pd.date_range('2026-01-01', periods=5, freq='h'),
        'soc': [50, 52, 54, 53, 51],
        'current': [1, 1, 1, -1, -1],
        'capacity_capacityDchCurrentCycle': [0, 0, 0, 0, 0],
        'capacity_capacityChCurrentCycle': [0, 1, 2, 2, 2],
    })
    assert detect_cycles(df) == []


class TestGoldenLog:
    """Regression guard against CLAUDE.md's documented observed results on a
    real E_BICK_LV_280 log: ~212Ah discharge / ~210Ah charge per full
    100%->20%/20%->100% cycle, matching theoretical Ah within ~99-100%."""

    @pytest.fixture(autouse=True)
    def _load(self, sample_log_csv_path):
        self.df = pd.read_csv(sample_log_csv_path, encoding='utf-8-sig')
        self.cycles = detect_cycles(self.df)

    def test_finds_three_cycles(self):
        assert len(self.cycles) == 3

    def test_cycle_kinds_alternate_discharge_charge_discharge(self):
        assert [c.kind for c in self.cycles] == ['discharge', 'charge', 'discharge']

    def test_full_cycles_span_roughly_80_percent_soc(self):
        for c in self.cycles:
            assert c.delta_soc >= 50.0

    def test_ah_matches_documented_range(self):
        for c in self.cycles:
            assert 200.0 <= c.ah <= 220.0

    def test_match_percent_within_documented_accuracy(self):
        for c in self.cycles:
            assert c.match_pct is not None
            assert 95.0 <= c.match_pct <= 105.0
