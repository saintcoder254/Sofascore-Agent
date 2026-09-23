from __future__ import annotations
import os
from typing import Any
from curl_cffi.requests import AsyncSession

class OddsApiClient:
    """Real bookmaker-market acquisition via The Odds API.

    Credentials are supplied at runtime; never stored in the repository.
    """
    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: str | None = None, regions: str | None = None,
                 timeout: float = 15):
        self.api_key = api_key or os.getenv("THE_ODDS_API_KEY")
        self.regions = regions or os.getenv("BASKETBALL_ODDS_REGIONS", "us")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("THE_ODDS_API_KEY is required for live odds acquisition")
        self.client = AsyncSession(
            impersonate="chrome",
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "EliteMatchMaster-Basketball/1.0"},
        )

    async def close(self):
        await self.client.close()

    async def odds(self, sport: str = "basketball_nba",
                   markets: str = "h2h,spreads,totals") -> dict[str, Any]:
        response = await self.client.get(
            f"{self.BASE_URL}/sports/{sport}/odds/",
            params={"apiKey": self.api_key, "regions": self.regions,
                    "markets": markets, "oddsFormat": "decimal", "dateFormat": "iso"},
        )
        response.raise_for_status()
        return {"data": response.json(), "headers": dict(response.headers)}

    async def historical_odds(self, sport: str, timestamp_iso: str,
                              markets: str = "h2h,spreads,totals") -> dict[str, Any]:
        response = await self.client.get(
            f"{self.BASE_URL}/historical/sports/{sport}/odds/",
            params={"apiKey": self.api_key, "regions": self.regions,
                    "markets": markets, "oddsFormat": "decimal",
                    "date": timestamp_iso},
        )
        response.raise_for_status()
        return {"data": response.json(), "headers": dict(response.headers)}

    @staticmethod
    def normalize_quotes(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        quotes: list[dict[str, Any]] = []
        for event in payload:
            for bookmaker in event.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        try:
                            quotes.append({
                                "provider_event_id": str(event["id"]),
                                "market": str(market["key"]),
                                "selection": str(outcome["name"]),
                                "odds": float(outcome["price"]),
                                "bookmaker": str(bookmaker.get("key", "unknown")),
                                "bookmaker_title": str(bookmaker.get("title", "")),
                                "last_update": str(market.get("last_update") or bookmaker.get("last_update", "")),
                                "home_team": str(event["home_team"]),
                                "away_team": str(event["away_team"]),
                                "commence_time": str(event["commence_time"]),
                            })
                        except (KeyError, TypeError, ValueError):
                            continue
        return quotes
