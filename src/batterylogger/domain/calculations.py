"""Pure numeric domain rules — no I/O, no state, fully unit-testable."""

from dataclasses import dataclass


def compute_derived_vcell(
    current: float,
    vcell_min: float,
    vcell_max: float,
    internal_resistance: float,
    num_cells: int,
    num_modules: int,
) -> tuple[float, float]:
    """Returns (cell_internal_resistance, corrected_vcell).

    Corrected vcell is IR-compensated: on discharge (current < 0) it estimates
    the true minimum cell voltage under load by adding the IR drop back to
    vcellMin; on charge it subtracts the drop from vcellMax.
    """
    if num_cells <= 0:
        return 0.0, 0.0
    total_cells = num_cells * num_modules
    cell_ir = internal_resistance / total_cells
    drop = abs(current) * cell_ir
    corrected = (vcell_min + drop) if current < 0 else (vcell_max - drop)
    return cell_ir, corrected


@dataclass(frozen=True)
class EnergyStats:
    energy_ch_wh: float = 0.0
    energy_dch_wh: float = 0.0


def accumulate_energy(stats: EnergyStats, power: float, dt_hours: float) -> EnergyStats:
    """Pure trapezoidal-ish energy accumulation: integrates `power` over `dt_hours`."""
    if power == 0 or dt_hours <= 0:
        return stats
    if power > 0:
        return EnergyStats(stats.energy_ch_wh + power * dt_hours, stats.energy_dch_wh)
    return EnergyStats(stats.energy_ch_wh, stats.energy_dch_wh + abs(power) * dt_hours)
