from __future__ import annotations
import asyncio
from .data_adapter import BasketballDataAdapter
from .store import BasketballStore
from .feature_builder import build_rolling_features

class BasketballCollector:
    """Collects real basketball observations without mixing them into football feeds."""
    def __init__(self, adapter: BasketballDataAdapter | None = None, store: BasketballStore | None = None):
        self.adapter = adapter or BasketballDataAdapter()
        self.store = store or BasketballStore()

    async def collect_date(self, date: str | None = None) -> dict:
        scheduled = await self.adapter.scheduled_events(date)
        events = scheduled.get("events", [])
        stored = 0
        for event in events:
            fixture_id = str(event.get("id", ""))
            if not fixture_id:
                continue
            self.store.put_raw("sofascore", fixture_id, self.adapter.payload_hash(event), event)
            stored += 1
        return {"events_seen": len(events), "events_stored": stored, "date": date}

    async def enrich_event(self, event_id: str | int) -> dict:
        fixture_id = str(event_id)
        event = await self.adapter.event(event_id)
        payloads = {"event": event}
        for name, loader in (
            ("statistics", self.adapter.event_statistics),
            ("incidents", self.adapter.event_incidents),
            ("lineups", self.adapter.event_lineups),
            ("shotmap", self.adapter.event_shotmap),
        ):
            try:
                payloads[name] = await loader(event_id)
            except Exception:
                payloads[name] = None
        self.store.put_raw("sofascore", fixture_id, self.adapter.payload_hash(payloads), payloads)
        return payloads

    async def close(self):
        await self.adapter.close()
