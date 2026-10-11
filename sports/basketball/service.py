from __future__ import annotations
import asyncio
from .collector import BasketballCollector

class BasketballDataService:
    """Operational polling loop for the isolated Basketball TITAN feed."""
    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = max(30, interval_seconds)
        self.collector = BasketballCollector()
        self.running = False
        self.last_result = None
        self.last_error = None

    async def collect_once(self):
        try:
            self.last_result = await self.collector.collect_date()
            self.last_error = None
            return self.last_result
        except Exception as exc:
            self.last_error = repr(exc)
            raise

    async def run(self):
        self.running = True
        while self.running:
            try:
                await self.collect_once()
            except Exception:
                pass
            await asyncio.sleep(self.interval_seconds)

    async def close(self):
        self.running = False
        await self.collector.close()
