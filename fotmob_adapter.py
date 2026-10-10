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

    async def events_for_date(self, day):
        """Fetch and normalize FotMob fixtures for an explicit UTC calendar date."""
        self.metrics["attempts"] += 1
        try:
            response = await self.client.get(
                self.BASE,
                params={"date": day.replace("-", "")},
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
            logger.error("FOTMOB_ERROR date=%s error=%r", day, exc)
            raise

    async def today_events(self):
        return await self.events_for_date(self._date())

    async def close(self):
        await self.client.aclose()



    async def team_details(self, team_id):
        """Fetch source-tagged FotMob team data used to derive recent-match history."""
        if team_id is None or not str(team_id).strip():
            raise ValueError("FotMob team_id is required")
        response = await self.client.get(
            f"{self.BASE}/teams",
            params={"id": str(team_id), "ccode3": "KEN"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("FotMob team endpoint returned invalid JSON shape")
        return {"source": "fotmob", "team_id": str(team_id),
                "retrieved_at": time.time(), "raw_payload": payload}

    @staticmethod
    def normalize_team_history(result, team_id):
        """Extract recent fixtures conservatively from a source-tagged team response."""
        if not isinstance(result, dict) or result.get("source") != "fotmob":
            raise ValueError("FotMob source-tagged team details are required")
        raw = result.get("raw_payload") or {}
        candidates = []
        def walk(node, depth=0):
            if depth > 5:
                return
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.lower() in {"fixtures", "matches", "lastmatches", "recentmatches"} and isinstance(value, list):
                        candidates.extend(x for x in value if isinstance(x, dict))
                    elif isinstance(value, (dict, list)):
                        walk(value, depth + 1)
            elif isinstance(node, list):
                for value in node:
                    if isinstance(value, (dict, list)):
                        walk(value, depth + 1)
        walk(raw)
        events = []
        seen = set()
        for item in candidates:
            normalized = FotMobAdapter._normalize_event(item)
            eid = normalized.get("source_event_id")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            home_id = str((normalized.get("homeTeam") or {}).get("id") or "")
            away_id = str((normalized.get("awayTeam") or {}).get("id") or "")
            if str(team_id) not in (home_id, away_id):
                continue
            events.append(normalized)
        return {"source": "fotmob", "team_id": str(team_id), "events": events[:20],
                "retrieved_at": result.get("retrieved_at", time.time()),
                **({"error": "FOTMOB_TEAM_HISTORY_UNAVAILABLE"} if not events else {})}

    async def external_odds(self, home_name, away_name, commence_time=None):
        """Query The Odds API only when explicitly configured; never synthesize prices."""
        import os
        import re
        api_key = os.getenv("THE_ODDS_API_KEY")
        sport_key = os.getenv("ODDS_API_SPORT_KEY", "soccer_austria_bundesliga")
        if not api_key:
            return {"source": "the_odds_api", "markets": [],
                    "error": "THE_ODDS_API_KEY_NOT_CONFIGURED", "retrieved_at": time.time()}
        response = await self.client.get(
            "https://api.the-odds-api.com/v4/sports/" + sport_key + "/odds/",
            params={"apiKey": api_key, "regions": os.getenv("ODDS_API_REGIONS", "eu"),
                    "markets": "h2h", "oddsFormat": "decimal"},
        )
        response.raise_for_status()
        payload = response.json()
        def canon(value):
            return re.sub(r"[^a-z0-9]", "", str(value or "").lower())
        target_home, target_away = canon(home_name), canon(away_name)
        def same(a, b):
            return bool(a and b and (a == b or a in b or b in a))
        matches = []
        for fixture in payload if isinstance(payload, list) else []:
            h, a = canon(fixture.get("home_team")), canon(fixture.get("away_team"))
            if not (same(target_home, h) and same(target_away, a)):
                continue
            for bookmaker in fixture.get("bookmakers", []) or []:
                for market in bookmaker.get("markets", []) or []:
                    if market.get("key") != "h2h":
                        continue
                    outcomes = [{"name": o.get("name"), "odds": o.get("price"),
                                 "decimalValue": o.get("price")}
                                for o in market.get("outcomes", []) or []
                                if isinstance(o.get("price"), (int, float)) and o.get("price") > 1]
                    if outcomes:
                        matches.append({"source": "the_odds_api", "bookmaker": bookmaker.get("key"),
                                        "market": "h2h", "choices": outcomes,
                                        "commence_time": fixture.get("commence_time"),
                                        "event_id": fixture.get("id")})
        return {"source": "the_odds_api", "markets": matches, "retrieved_at": time.time(),
                **({"error": "ODDS_FIXTURE_NOT_FOUND"} if not matches else {})}

    @staticmethod
    def normalize_match_details(result):
        """Normalize documented FotMob matchDetails sections into the acquisition schema.

        Missing sections remain explicit errors; they are never filled with
        fabricated values or interpreted as SofaScore payloads.
        """
        import datetime
        import time

        if not isinstance(result, dict) or result.get("source") != "fotmob":
            raise ValueError("FotMob source-tagged match details are required")
        raw = result.get("raw_payload")
        if not isinstance(raw, dict) or not raw:
            raise ValueError("FotMob raw payload is missing")
        general = raw.get("general") or {}
        header = raw.get("header") or {}
        content = raw.get("content") or {}
        teams = header.get("teams") or []
        home = general.get("homeTeam") or (teams[0] if len(teams) > 0 else {})
        away = general.get("awayTeam") or (teams[1] if len(teams) > 1 else {})
        status = header.get("status") or {}
        reason = status.get("reason") or {}
        state = ("finished" if status.get("finished") or general.get("finished") else
                 "inprogress" if status.get("started") or general.get("started") else
                 "notstarted")
        if status.get("cancelled"):
            state = "cancelled"
        event = {
            "id": "fotmob:" + str(general.get("matchId") or result.get("source_event_id")),
            "source": "fotmob",
            "source_event_id": str(general.get("matchId") or result.get("source_event_id") or ""),
            "date": general.get("matchTimeUTCDate") or status.get("utcTime"),
            "name": general.get("matchName"),
            "status": {"type": {"state": state, "description": reason.get("long") or reason.get("short")}},
            "homeTeam": {"id": str(home.get("id") or ""), "name": home.get("name"), "score": home.get("score")},
            "awayTeam": {"id": str(away.get("id") or ""), "name": away.get("name"), "score": away.get("score")},
            "competition": {"name": general.get("leagueName"), "id": general.get("leagueId")},
            "normalization_state": "NORMALIZED",
            "raw_source_payload": {"general": general, "header": header},
        }

        stats_root = ((content.get("stats") or {}).get("Periods") or {}).get("All") or {}
        stat_groups = stats_root.get("stats") or []
        statistics = {"source": "fotmob", "period": "All", "groups": stat_groups}
        if not stat_groups:
            statistics["error"] = "FOTMOB_STATS_UNAVAILABLE"

        lineup = content.get("lineup") or {}
        lineup_home = lineup.get("homeTeam")
        lineup_away = lineup.get("awayTeam")
        if not lineup_home or not lineup_away:
            lineups = lineup.get("lineups") or []
            for item in lineups:
                tid = str(item.get("teamId") or item.get("id") or "")
                if tid and tid == str(home.get("id") or ""):
                    lineup_home = item
                elif tid and tid == str(away.get("id") or ""):
                    lineup_away = item
        normalized_lineups = {"source": "fotmob", "home": lineup_home, "away": lineup_away}
        if not lineup_home and not lineup_away:
            normalized_lineups["error"] = "FOTMOB_LINEUPS_UNAVAILABLE"

        facts = content.get("matchFacts") or {}
        event_root = facts.get("events") or {}
        incidents = event_root.get("events") if isinstance(event_root, dict) else None
        if incidents is None:
            incidents = header.get("events")
        normalized_incidents = {"source": "fotmob", "events": incidents or []}
        if incidents is None:
            normalized_incidents["error"] = "FOTMOB_INCIDENTS_UNAVAILABLE"

        shotmap = content.get("shotmap") or {}
        normalized_shotmap = {"source": "fotmob", "shots": shotmap.get("shots") or []}
        if not shotmap.get("shots"):
            normalized_shotmap["error"] = "FOTMOB_SHOTMAP_UNAVAILABLE"

        h2h = content.get("h2h") or {}
        if not h2h:
            h2h = {"error": "FOTMOB_H2H_UNAVAILABLE", "source": "fotmob"}
        else:
            h2h = {"source": "fotmob", **h2h}

        retrieved_at = result.get("retrieved_at") or time.time()
        return {
            "event": event,
            "statistics": statistics,
            "shotmap": normalized_shotmap,
            "incidents": normalized_incidents,
            "lineups": normalized_lineups,
            "h2h": h2h,
            "history": {"home": {"events": [], "error": "FOTMOB_TEAM_HISTORY_UNAVAILABLE"},
                        "away": {"events": [], "error": "FOTMOB_TEAM_HISTORY_UNAVAILABLE"}},
            "odds": {"1": {"error": "FOTMOB_MARKET_ODDS_UNAVAILABLE"},
                     "2": {"error": "FOTMOB_MARKET_ODDS_UNAVAILABLE"}},
            "verification": {"events": [], "error": "INDEPENDENT_VERIFICATION_REQUIRED"},
            "final_results": {"sources": []},
            "fotmob_raw": result,
            "data_trust": {"state": "QUARANTINED",
                           "hard_blocks": ["ALTERNATE_SOURCE_EVIDENCE_REQUIRES_INDEPENDENT_VERIFICATION",
                                           "FOTMOB_MARKET_ODDS_UNAVAILABLE",
                                           "FOTMOB_TEAM_HISTORY_UNAVAILABLE"]},
            "retrieved_at": retrieved_at,
        }

    async def match_details(self, match_id):
        """Fetch raw FotMob match details without pretending they are SofaScore data.

        The returned payload is intentionally source-tagged and unmodified.
        Downstream normalization must validate each required evidence section
        before UMIOS can qualify a fixture.
        """
        if match_id is None or not str(match_id).strip():
            raise ValueError("FotMob match_id is required")
        self.metrics["attempts"] += 1
        try:
            response = await self.client.get(
                f"{self.BASE}/matchDetails",
                params={"matchId": str(match_id)},
            )
            self.metrics["last_status_code"] = response.status_code
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not payload:
                raise RuntimeError("FotMob returned an empty or invalid match-details payload")
            retrieved_at = time.time()
            self.metrics["success"] += 1
            self.metrics["last_success_at"] = retrieved_at
            self.metrics["last_error"] = None
            return {
                "source": "fotmob",
                "source_event_id": str(match_id),
                "retrieved_at": retrieved_at,
                "raw_payload": payload,
                "normalization_state": "RAW_UNNORMALIZED",
            }
        except Exception as exc:
            self.metrics["failures"] += 1
            self.metrics["last_error"] = repr(exc)
            logger.error("FOTMOB_MATCH_DETAILS_ERROR match_id=%s error=%r", match_id, exc)
            raise
