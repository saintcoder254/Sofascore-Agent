from __future__ import annotations
import asyncio
import time
from .odds_api import OddsApiClient
from .market_adapter import BasketballMarketAdapter
from .market_store import BasketballMarketStore

class BasketballMarketService:
    """Operational odds collector. No-op until THE_ODDS_API_KEY is configured."""
    def __init__(self, store: BasketballMarketStore, interval_seconds: int = 60):
        self.store = store
        self.interval_seconds = max(60, interval_seconds)
        self.adapter = BasketballMarketAdapter()

    async def collect_once(self, sports: list[str] | None = None):
        sports = sports or ["basketball_nba", "basketball_wnba", "basketball_ncaab"]
        collected = 0
        for sport in sports:
            client = OddsApiClient()
            try:
                response = await client.odds(sport=sport)
                quotes = client.normalize_quotes(response["data"])
                now = time.time()
                for quote in quotes:
                    # The market store remains the audit boundary; provider event IDs
                    # are retained in the source string until fixture reconciliation.
                    fixture_id = quote["provider_event_id"]
                    normalized = self.adapter.normalize(
                        fixture_id=fixture_id,
                        source=f"the-odds-api:{quote['bookmaker']}",
                        payload={"quotes": [{
                            "market": quote["market"],
                            "selection": quote["selection"],
                            "odds": quote["odds"],
                            "is_closing": False,
                        }]},
                        captured_at=now,
                    )
                    for snapshot in normalized:
                        self.store.put(snapshot)
                        collected += 1
            finally:
                await client.close()
        return collected

    async def run_forever(self):
        while True:
            try:
                await self.collect_once()
            except Exception:
                # Acquisition failures must not stop the model service.
                pass
            await asyncio.sleep(self.interval_seconds)
