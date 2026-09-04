"""Real-world time adapters — thin wrappers so use-cases can be tested
without real wall-clock waits (tests inject a fake ClockPort/SleeperPort)."""

import asyncio
from datetime import datetime


class SystemClock:
    """Implements domain.ports.ClockPort."""

    def now(self) -> datetime:
        return datetime.now()


class AsyncSleeper:
    """Implements domain.ports.SleeperPort."""

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
