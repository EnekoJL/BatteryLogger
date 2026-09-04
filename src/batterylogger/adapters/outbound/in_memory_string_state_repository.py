"""In-memory, asyncio-lock-guarded per-string state store.

Mirrors in_memory_state_repository.py's pattern, keyed by string_id. No
derived calculations at string level (the BMS payload for a string doesn't
carry the pack-level SOP/energy concerns) — just a pure merge per ID behind
one lock.
"""

import asyncio

from batterylogger.domain.string_reading import StringReading, apply_string_update


class InMemoryStringStateRepository:
    """Implements domain.ports.StringStateRepository."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._readings: dict[int, StringReading] = {}

    async def update(self, string_id: int, patch: dict) -> StringReading:
        async with self._lock:
            current = self._readings.get(string_id, StringReading())
            updated = apply_string_update(current, patch)
            self._readings[string_id] = updated
            return updated

    async def get_snapshot(self, string_id: int) -> StringReading | None:
        async with self._lock:
            return self._readings.get(string_id)

    async def get_all_snapshots(self) -> dict[int, StringReading]:
        async with self._lock:
            return dict(self._readings)
