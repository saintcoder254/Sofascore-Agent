import datetime
import logging
import time

import httpx

from sofascore_adapter import SofaScoreAdapter
from fotmob_adapter import FotMobAdapter
from futbol24_adapter import Futbol24Adapter

logger = logging.getLogger("emm.fusion")


class FeedFusionAdapter:
    """Multi-source football acquisition with ordered failover and verification.

    Acquisition priority: SofaScore -> ESPN -> FotMob.
    Futbol24 is additionally queried as an independent verification source.
    Its data is not blindly promoted when it conflicts with the active feed.
    """

    ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"

    def __init__(self, sofascore_base, timeout=15):
        self.primary = SofaScoreAdapter(sofascore_base, timeout)
        self.fotmob = FotMobAdapter(timeout)
        self.futbol24 = Futbol24Adapter(timeout)
        self.timeout = timeout
        self.fallback_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "EliteMatchMaster/1.0 feed-fusion"},
        )
        self.active_source = None
        self.last_fallback_error = None
        self.metrics = {
            "primary_attempts": 0, "primary_success": 0, "primary_failures": 0,
            "espn_attempts": 0, "espn_success": 0, "espn_failures": 0,
            "fotmob_attempts": 0, "fotmob_success": 0, "fotmob_failures": 0,
            "futbol24_attempts": 0, "futbol24_success": 0, "futbol24_failures": 0,
            "futbol24_verification_events": 0,
            "futbol24_score_conflicts": 0,
            "last_futbol24_at": None,
            "last_source": None, "last_error": None, "last_success_at": None,
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
                "id": str(event.get("id", "")), "source": "espn",
                "source_event_id": str(event.get("id", "")), "source_retrieved_at": time.time(),
                "date": event.get("date"), "name": event.get("name"), "shortName": event.get("shortName"),
                "status": status,
                "homeTeam": {"id": str((home.get("team") or {}).get("id", "")), "name": (home.get("team") or {}).get("displayName"), "shortName": (home.get("team") or {}).get("shortDisplayName"), "score": home.get("score")},
                "awayTeam": {"id": str((away.get("team") or {}).get("id", "")), "name": (away.get("team") or {}).get("displayName"), "shortName": (away.get("team") or {}).get("shortDisplayName"), "score": away.get("score")},
                "competition": competition.get("league") or {}, "raw_source_payload": event,
            })
        return {"source": "espn", "source_priority": 2, "retrieved_at": time.time(), "date": payload.get("day", {}).get("date") or FeedFusionAdapter._date(), "events": events}

    async def _fallback_espn(self):
        self.metrics["espn_attempts"] += 1
        day = self._date().replace("-", "")
        try:
            response = await self.fallback_client.get(self.ESPN_BASE, params={"dates": day})
            response.raise_for_status()
            normalized = self._normalize_espn(response.json())
            if not normalized["events"]: raise RuntimeError("ESPN returned no match events")
            self.metrics["espn_success"] += 1; self.metrics["last_source"] = "espn"; self.metrics["last_success_at"] = time.time(); self.metrics["last_error"] = None; self.active_source = "espn"
            logger.warning("FUSION_FALLBACK_SUCCESS source=espn events=%s date=%s", len(normalized["events"]), self._date())
            return normalized
        except Exception as exc:
            self.metrics["espn_failures"] += 1; self.metrics["last_error"] = repr(exc); logger.error("FUSION_FALLBACK_ERROR source=espn error=%r", exc); raise

    async def _fallback_fotmob(self):
        self.metrics["fotmob_attempts"] += 1
        try:
            normalized = await self.fotmob.today_events()
            self.metrics["fotmob_success"] += 1; self.metrics["last_source"] = "fotmob"; self.metrics["last_success_at"] = time.time(); self.metrics["last_error"] = None; self.active_source = "fotmob"
            logger.warning("FUSION_FALLBACK_SUCCESS source=fotmob events=%s date=%s", len(normalized["events"]), self._date())
            return normalized
        except Exception as exc:
            self.metrics["fotmob_failures"] += 1; self.metrics["last_error"] = repr(exc); logger.error("FUSION_FALLBACK_ERROR source=fotmob error=%r", exc); raise

    async def verify_futbol24(self):
        """Query Futbol24 independently and return verification observations."""
        self.metrics["futbol24_attempts"] += 1
        try:
            payload = await self.futbol24.today_events()
            events = payload.get("events", [])
            self.metrics["futbol24_success"] += 1
            self.metrics["futbol24_verification_events"] = len(events)
            self.metrics["last_futbol24_at"] = time.time()
            logger.info("FUTBOL24_VERIFY_SUCCESS events=%s", len(events))
            return payload
        except Exception as exc:
            self.metrics["futbol24_failures"] += 1
            logger.warning("FUTBOL24_VERIFY_FAILED error=%r", exc)
            return {"source": "futbol24", "source_priority": 4, "retrieved_at": time.time(), "date": self._date(), "events": [], "error": repr(exc)}

    @staticmethod
    def _team_key(team):
        return str((team or {}).get("name") or "").strip().lower()

    def reconcile_scores(self, active_payload, verification_payload):
        """Compare recognizable score observations without replacing active data."""
        conflicts = []
        active_events = active_payload.get("events", []) if active_payload else []
        verify_events = verification_payload.get("events", []) if verification_payload else []
        for ve in verify_events:
            vh, va = ve.get("homeTeam") or {}, ve.get("awayTeam") or {}
            if vh.get("score") is None or va.get("score") is None:
                continue
            for ae in active_events:
                ah, aa = ae.get("homeTeam") or {}, ae.get("awayTeam") or {}
                if self._team_key(vh) == self._team_key(ah) and self._team_key(va) == self._team_key(aa):
                    if (str(vh.get("score")), str(va.get("score"))) != (str(ah.get("score")), str(aa.get("score"))):
                        conflicts.append({"active_id": ae.get("id"), "verification_id": ve.get("id"), "active_score": [ah.get("score"), aa.get("score")], "futbol24_score": [vh.get("score"), va.get("score")]})
        self.metrics["futbol24_score_conflicts"] += len(conflicts)
        if conflicts:
            logger.warning("FUTBOL24_SCORE_CONFLICTS count=%s", len(conflicts))
        return conflicts

    async def today_events(self):
        self.metrics["primary_attempts"] += 1
        try:
            payload = await self.primary.today_events()
            payload["source"] = "sofascore"; payload["source_priority"] = 1; payload["retrieved_at"] = time.time()
            self.metrics["primary_success"] += 1; self.metrics["last_source"] = "sofascore"; self.metrics["last_success_at"] = time.time(); self.metrics["last_error"] = None; self.active_source = "sofascore"
            logger.info("FUSION_PRIMARY_SUCCESS source=sofascore events=%s", len(payload.get("events", [])))
        except Exception as primary_exc:
            self.metrics["primary_failures"] += 1; self.metrics["last_error"] = repr(primary_exc)
            logger.warning("FUSION_PRIMARY_FAILED source=sofascore error=%r; trying espn", primary_exc)
            try:
                payload = await self._fallback_espn()
            except Exception as espn_exc:
                logger.warning("FUSION_SECONDARY_FAILED source=espn error=%r; trying fotmob", espn_exc)
                try:
                    payload = await self._fallback_fotmob()
                except Exception as fotmob_exc:
                    self.last_fallback_error = repr(fotmob_exc)
                    logger.error("FUSION_ALL_SOURCES_FAILED sofascore=%r espn=%r fotmob=%r", primary_exc, espn_exc, fotmob_exc)
                    raise RuntimeError("All football acquisition sources failed") from fotmob_exc

        # Hard-wired independent verification on every acquisition cycle.
        verification = await self.verify_futbol24()
        payload["verification"] = {"futbol24": verification}
        payload["verification_conflicts"] = self.reconcile_scores(payload, verification)
        return payload

    def payload_hash(self, payload):
        return self.primary.payload_hash(payload)

    async def close(self):
        await self.primary.close()
        await self.fotmob.close()
        await self.futbol24.close()
        await self.fallback_client.aclose()
