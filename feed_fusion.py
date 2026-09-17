import datetime
import logging
import time

import httpx

from sofascore_adapter import SofaScoreAdapter

logger = logging.getLogger("emm.fusion")


class FeedFusionAdapter:
    """Primary SofaScore acquisition with an independent ESPN fallback.

    The fallback is deliberately source-labelled so downstream UMIOS can
    distinguish primary and fallback observations instead of treating them as
    interchangeable facts.
    """

    ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"

    def __init__(self, sofascore_base, timeout=15):
        self.primary = SofaScoreAdapter(sofascore_base, timeout)
        self.timeout = timeout
        self.fallback_client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "EliteMatchMaster/1.0 feed-fusion",
            },
        )
        self.active_source = None
        self.last_fallback_error = None
        self.metrics = {
            "primary_attempts": 0,
            "primary_success": 0,
            "primary_failures": 0,
            "fallback_attempts": 0,
            "fallback_success": 0,
            "fallback_failures": 0,
            "last_source": None,
            "last_error": None,
            "last_success_at": None,
        }

    @property
    def primary_metrics(self):
        return self.primary.metrics

    @staticmethod
    def _date():
        return datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    @staticmethod
    def _normalize_espn(payload):
        events = []
        for event in payload.get("events", []):
            competitions = event.get("competitions") or []
            competition = competitions[0] if competitions else {}
            competitors = competition.get("competitors") or []
            home = next((c for c in competitors if c.get("homeAway") == "home"), {})
            away = next((c for c in competitors if c.get("homeAway") == "away"), {})
            status = (event.get("status") or {}).get("type") or {}
            events.append({
                "id": str(event.get("id", "")),
                "source": "espn",
                "source_event_id": str(event.get("id", "")),
                "source_retrieved_at": time.time(),
                "date": event.get("date"),
                "name": event.get("name"),
                "shortName": event.get("shortName"),
                "status": status,
                "homeTeam": {
                    "id": str((home.get("team") or {}).get("id", "")),
                    "name": (home.get("team") or {}).get("displayName"),
                    "shortName": (home.get("team") or {}).get("shortDisplayName"),
                    "score": home.get("score"),
                },
                "awayTeam": {
                    "id": str((away.get("team") or {}).get("id", "")),
                    "name": (away.get("team") or {}).get("displayName"),
                    "shortName": (away.get("team") or {}).get("shortDisplayName"),
                    "score": away.get("score"),
                },
                "competition": competition.get("league") or {},
                "raw_source_payload": event,
            })
        return {
            "source": "espn",
            "source_priority": 2,
            "retrieved_at": time.time(),
            "date": payload.get("day", {}).get("date") or FeedFusionAdapter._date(),
            "events": events,
        }

    async def _fallback_today(self):
        self.metrics["fallback_attempts"] += 1
        day = self._date().replace("-", "")
        try:
            response = await self.fallback_client.get(
                self.ESPN_BASE,
                params={"dates": day},
            )
            response.raise_for_status()
            payload = response.json()
            normalized = self._normalize_espn(payload)
            self.metrics["fallback_success"] += 1
            self.metrics["last_source"] = "espn"
            self.metrics["last_success_at"] = time.time()
            self.metrics["last_error"] = None
            self.active_source = "espn"
            logger.warning(
                "FUSION_FALLBACK_SUCCESS source=espn events=%s date=%s",
                len(normalized["events"]), self._date(),
            )
            return normalized
        except Exception as exc:
            self.metrics["fallback_failures"] += 1
            self.last_fallback_error = repr(exc)
            self.metrics["last_error"] = repr(exc)
            logger.error("FUSION_FALLBACK_ERROR source=espn error=%r", exc)
            raise

    async def today_events(self):
        self.metrics["primary_attempts"] += 1
        try:
            payload = await self.primary.today_events()
            payload["source"] = "sofascore"
            payload["source_priority"] = 1
            payload["retrieved_at"] = time.time()
            self.metrics["primary_success"] += 1
            self.metrics["last_source"] = "sofascore"
            self.metrics["last_success_at"] = time.time()
            self.metrics["last_error"] = None
            self.active_source = "sofascore"
            logger.info("FUSION_PRIMARY_SUCCESS source=sofascore events=%s", len(payload.get("events", [])))
            return payload
        except Exception as exc:
            self.metrics["primary_failures"] += 1
            self.metrics["last_error"] = repr(exc)
            logger.warning("FUSION_PRIMARY_FAILED source=sofascore error=%r; trying fallback", exc)
            return await self._fallback_today()

    def payload_hash(self, payload):
        return self.primary.payload_hash(payload)

    async def close(self):
        await self.primary.close()
        await self.fallback_client.aclose()
