"""In-memory, asyncio-lock-guarded battery state store.

This is where concurrency control lives (locking is an infrastructure
concern) — it delegates all actual math to pure domain functions
(entities.apply_update, calculations.compute_derived_vcell/accumulate_energy).

Because BatteryReading and its nested value objects are frozen dataclasses,
handing out a snapshot needs no copy.deepcopy — an immutable object can't be
mutated by the caller, so sharing the reference is safe.
"""

import asyncio
import dataclasses
from datetime import datetime
from typing import Optional

from batterylogger.domain.calculations import EnergyStats, accumulate_energy, compute_derived_vcell
from batterylogger.domain.config import BatteryTopology
from batterylogger.domain.entities import BatteryReading, apply_update
from batterylogger.domain.ports import ClockPort


class InMemoryStateRepository:
    """Implements domain.ports.BatteryStateRepository."""

    def __init__(self, topology: BatteryTopology, clock: ClockPort):
        self._lock = asyncio.Lock()
        self._reading = BatteryReading()
        self._topology = topology
        self._clock = clock
        self._energy = EnergyStats()
        self._last_update_time: Optional[datetime] = None

    async def update(self, patch: dict) -> BatteryReading:
        async with self._lock:
            reading = apply_update(self._reading, patch)

            cell_ir, corrected = compute_derived_vcell(
                current=reading.current,
                vcell_min=reading.vcell.vcellMin,
                vcell_max=reading.vcell.vcellMax,
                internal_resistance=reading.vcell.internalResistance,
                num_cells=self._topology.num_cells,
                num_modules=self._topology.num_modules,
            )
            reading = dataclasses.replace(
                reading,
                vcell=dataclasses.replace(
                    reading.vcell,
                    cellInternalResistance=cell_ir,
                    corrected_vcell=corrected,
                ),
            )

            now = self._clock.now()
            if self._last_update_time is not None:
                dt_hours = (now - self._last_update_time).total_seconds() / 3600.0
                self._energy = accumulate_energy(self._energy, reading.power, dt_hours)
            self._last_update_time = now

            self._reading = reading
            return reading

    async def get_snapshot(self) -> BatteryReading:
        async with self._lock:
            return self._reading

    async def get_energy_stats(self) -> EnergyStats:
        async with self._lock:
            return self._energy
