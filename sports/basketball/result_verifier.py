from __future__ import annotations
import datetime as dt
from curl_cffi.requests import AsyncSession

class ESPNResultVerifier:
    """Independent postgame result verifier.

    ESPN is deliberately used only as a verification boundary, not as the
    primary feature source. NBA/WNBA/NCAAB can be selected explicitly.
    """
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball"

    def __init__(self, league: str = "nba", timeout: float = 15):
        self.league = league
        self.client = AsyncSession(
            impersonate="chrome",
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "EliteMatchMaster-Basketball/1.0"},
        )

    async def close(self):
        await self.client.close()

    async def scoreboard(self, date: str | None = None) -> dict:
        day = date or dt.datetime.now(dt.timezone.utc).date().isoformat()
        response = await self.client.get(
            f"{self.BASE_URL}/{self.league}/scoreboard",
            params={"dates": day.replace("-", "")},
        )
        response.raise_for_status()
        return response.json()

    async def completed_results(self, date: str | None = None) -> list[dict]:
        payload = await self.scoreboard(date)
        results = []
        for event in payload.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            status = competition.get("status", {}).get("type", {})
            if not status.get("completed"):
                continue
            competitors = competition.get("competitors", [])
            home = next((x for x in competitors if x.get("homeAway") == "home"), None)
            away = next((x for x in competitors if x.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            try:
                hs, aws = float(home["score"]), float(away["score"])
            except (KeyError, TypeError, ValueError):
                continue
            results.append({
                "provider_event_id": str(event["id"]),
                "home_team": home.get("team", {}).get("displayName", ""),
                "away_team": away.get("team", {}).get("displayName", ""),
                "home_score": hs,
                "away_score": aws,
                "total": hs + aws,
                "home_win": int(hs > aws),
                "completed": True,
            })
        return results
