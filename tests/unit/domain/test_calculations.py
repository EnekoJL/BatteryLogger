from batterylogger.domain.calculations import EnergyStats, accumulate_energy, compute_derived_vcell


class TestComputeDerivedVcell:
    def test_num_cells_zero_returns_zeros(self):
        cell_ir, corrected = compute_derived_vcell(
            current=-10.0, vcell_min=3300, vcell_max=3400,
            internal_resistance=1.5, num_cells=0, num_modules=1,
        )
        assert cell_ir == 0.0
        assert corrected == 0.0

    def test_discharge_adds_drop_to_vcell_min(self):
        # current < 0 => discharge => corrected = vcellMin + drop
        cell_ir, corrected = compute_derived_vcell(
            current=-20.0, vcell_min=3300, vcell_max=3400,
            internal_resistance=15.0, num_cells=15, num_modules=1,
        )
        assert cell_ir == 1.0  # 15.0 / (15*1)
        assert corrected == 3300 + 20.0 * 1.0

    def test_charge_subtracts_drop_from_vcell_max(self):
        # current >= 0 => charge => corrected = vcellMax - drop
        cell_ir, corrected = compute_derived_vcell(
            current=20.0, vcell_min=3300, vcell_max=3400,
            internal_resistance=15.0, num_cells=15, num_modules=1,
        )
        assert cell_ir == 1.0
        assert corrected == 3400 - 20.0 * 1.0

    def test_current_zero_treated_as_charge_branch(self):
        _, corrected = compute_derived_vcell(
            current=0.0, vcell_min=3300, vcell_max=3400,
            internal_resistance=0.0, num_cells=15, num_modules=1,
        )
        assert corrected == 3400  # drop is 0, charge branch (current < 0 is False)

    def test_multiple_modules_divides_total_cells(self):
        cell_ir, _ = compute_derived_vcell(
            current=0.0, vcell_min=0, vcell_max=0,
            internal_resistance=30.0, num_cells=15, num_modules=2,
        )
        assert cell_ir == 1.0  # 30.0 / (15*2)


class TestAccumulateEnergy:
    def test_zero_power_is_noop(self):
        stats = EnergyStats(energy_ch_wh=5.0, energy_dch_wh=2.0)
        assert accumulate_energy(stats, power=0.0, dt_hours=1.0) == stats

    def test_zero_or_negative_dt_is_noop(self):
        stats = EnergyStats()
        assert accumulate_energy(stats, power=100.0, dt_hours=0.0) == stats
        assert accumulate_energy(stats, power=100.0, dt_hours=-1.0) == stats

    def test_positive_power_accumulates_charge(self):
        stats = EnergyStats()
        new_stats = accumulate_energy(stats, power=100.0, dt_hours=0.5)
        assert new_stats.energy_ch_wh == 50.0
        assert new_stats.energy_dch_wh == 0.0

    def test_negative_power_accumulates_discharge(self):
        stats = EnergyStats()
        new_stats = accumulate_energy(stats, power=-200.0, dt_hours=0.25)
        assert new_stats.energy_ch_wh == 0.0
        assert new_stats.energy_dch_wh == 50.0

    def test_does_not_mutate_input(self):
        stats = EnergyStats(1.0, 2.0)
        accumulate_energy(stats, power=100.0, dt_hours=1.0)
        assert stats == EnergyStats(1.0, 2.0)
