import datetime
import logging
import time

import httpx

logger = logging.getLogger("emm.fotmob")


class FotMobAdapter:
    """Independent FotMob fallback adapter.

    FotMob is used only after the primary SofaScore feed and ESPN fallback
    fail. The adapter keeps the raw event payload attached for downstream
    reconciliation and source-quality scoring.
    """

    BASE = "https://www.fotmob.com/api/data"

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
                "Referer": "https://www.fotmob.com/",
            },
        )
        self.metrics = {
            "attempts": 0,
            "success": 0,
            "failures": 0,
            "last_status_code": None,
            "last_success_at": None,
            "last_error": None,
        }

    @staticmethod
    def _date():
        return datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    @staticmethod
    def _team(obj):
        obj = obj or {}
        return {
            "id": str(obj.get("id") or obj.get("teamId") or ""),
            "name": obj.get("name") or obj.get("teamName") or obj.get("longName"),
            "shortName": obj.get("shortName") or obj.get("short_name") or obj.get("name"),
            "score": obj.get("score") if obj.get("score") is not None else obj.get("goals"),
        }

    @classmethod
    def _normalize_event(cls, event):
        # FotMob has used a few closely related shapes over time. Handle the
        # common match-list representations without assuming one schema.
        home = event.get("home") or event.get("homeTeam") or {}
        away = event.get("away") or event.get("awayTeam") or {}
        if isinstance(home, dict) and "team" in home:
            home = home.get("team") or home
        if isinstance(away, dict) and "team" in away:
            away = away.get("team") or away

        status = event.get("status") or {}
        if isinstance(status, str):
            status = {"name": status}

        eid = event.get("id") or event.get("matchId") or event.get("match_id")
        return {
            "id": f"fotmob:{eid}" if eid is not None else "",
            "source": "fotmob",
            "source_event_id": str(eid or ""),
            "source_retrieved_at": time.time(),
            "date": event.get("date") or event.get("utcTime") or event.get("startTime"),
            "name": event.get("name") or event.get("matchName"),
            "shortName": event.get("shortName"),
            "status": status,
            "homeTeam": cls._team(home),
            "awayTeam": cls._team(away),
            "competition": event.get("tournament") or event.get("league") or event.get("competition") or {},
            "raw_source_payload": event,
        }

    @classmethod
    def _extract_events(cls, payload):
        candidates = []
        if isinstance(payload, dict):
            for key in ("matches", "events", "fixtures"):
                value = payload.get(key)
                if isinstance(value, list):
                    candidates.extend(value)
            for key in ("leagues", "matchesByLeague", "fixturesByLeague"):
                groups = payload.get(key)
                if isinstance(groups, list):
                    for group in groups:
                        if isinstance(group, dict):
                            for subkey in ("matches", "events", "fixtures"):
                                value = group.get(subkey)
                                if isinstance(value, list):
                                    candidates.extend(value)
        # De-duplicate by source match id while retaining first occurrence.
        seen = set()
        result = []
        for event in candidates:
            if not isinstance(event, dict):
                continue
            normalized = cls._normalize_event(event)
            if not normalized["source_event_id"] or normalized["source_event_id"] in seen:
                continue
            seen.add(normalized["source_event_id"])
            result.append(normalized)
        return result

    async def today_events(self):
        self.metrics["attempts"] += 1
        day = self._date()
        try:
            response = await self.client.get(
                self.BASE,
                params={"type": "matches", "date": day},
            )
            self.metrics["last_status_code"] = response.status_code
            response.raise_for_status()
            payload = response.json()
            events = self._extract_events(payload)
            if not events:
                raise RuntimeError("FotMob returned no parseable match events")
            self.metrics["success"] += 1
            self.metrics["last_success_at"] = time.time()
            self.metrics["last_error"] = None
            logger.warning("FOTMOB_SUCCESS events=%s date=%s", len(events), day)
            return {
                "source": "fotmob",
                "source_priority": 3,
                "retrieved_at": time.time(),
                "date": day,
                "events": events,
            }
        except Exception as exc:
            self.metrics["failures"] += 1
            self.metrics["last_error"] = repr(exc)
            logger.error("FOTMOB_ERROR error=%r", exc)
            raise

    async def close(self):
        await self.client.aclose()
