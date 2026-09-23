from __future__ import annotations
import datetime as dt
import hashlib
import json
import logging
import time
from curl_cffi.requests import AsyncSession

logger = logging.getLogger("emm.basketball.data")

class BasketballDataAdapter:
    """Live/historical basketball acquisition boundary.

    This adapter deliberately stays separate from the football acquisition pipeline.
    It uses the same HTTP conventions as the repository's SofaScore adapter and
    preserves raw payloads so later feature builders can be audited.
    """
    def __init__(self, base_url: str = "https://www.sofascore.com/api/v1", timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = AsyncSession(
            impersonate="chrome",
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.sofascore.com/",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        self.metrics = {"requests": 0, "success": 0, "failed": 0, "last_path": None, "last_error": None}

    async def close(self):
        await self.client.close()

    async def get_json(self, path: str):
        self.metrics["requests"] += 1
        self.metrics["last_path"] = path
        try:
            response = await self.client.get(f"{self.base_url}/{path.lstrip('/')}")
            response.raise_for_status()
            payload = response.json()
            self.metrics["success"] += 1
            return payload
        except Exception as exc:
            self.metrics["failed"] += 1
            self.metrics["last_error"] = repr(exc)
            raise

    async def scheduled_events(self, date: str | None = None):
        day = date or dt.datetime.now(dt.timezone.utc).date().isoformat()
        return await self.get_json(f"/sport/basketball/scheduled-events/{day}")

    async def event(self, event_id: str | int):
        return await self.get_json(f"/event/{event_id}")

    async def event_statistics(self, event_id: str | int):
        return await self.get_json(f"/event/{event_id}/statistics")

    async def event_incidents(self, event_id: str | int):
        return await self.get_json(f"/event/{event_id}/incidents")

    async def event_lineups(self, event_id: str | int):
        return await self.get_json(f"/event/{event_id}/lineups")

    async def event_shotmap(self, event_id: str | int):
        return await self.get_json(f"/event/{event_id}/shotmap")

    async def team_events(self, team_id: str | int, page: int = 0):
        return await self.get_json(f"/team/{team_id}/events/last/{page}")

    async def team_next_events(self, team_id: str | int, page: int = 0):
        return await self.get_json(f"/team/{team_id}/events/next/{page}")

    @staticmethod
    def payload_hash(payload: object) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
