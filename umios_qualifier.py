import datetime, math, re, time

class UMIOSQualifier:
    REQUIRED = ("event", "lineups", "statistics", "incidents")
    PREMATCH_STATES = {"notstarted", "not_started", "not started", "scheduled", "upcoming", "created"}
    MIN_INDEPENDENT_VERIFICATION_SOURCES = 2

    def __init__(self, stale_after=180):
        self.stale_after = stale_after

    @staticmethod
    def _err(x):
        return isinstance(x, dict) and bool(x.get("error"))

    @staticmethod
    def _norm(x):
        return re.sub(r"[^a-z0-9]+", "", str(x or "").casefold())

    @staticmethod
    def _name(x):
        return str(x.get("name") or "").strip() if isinstance(x, dict) else ""

    @staticmethod
    def _timestamp(x):
        if x is None or isinstance(x, bool):
            return None
        try:
            n = float(x)
            if math.isfinite(n):
                return n
        except (TypeError, ValueError, OverflowError):
            pass
        if isinstance(x, str):
            try:
                d = datetime.datetime.fromisoformat(x.strip().replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=datetime.timezone.utc)
                return d.timestamp()
            except (TypeError, ValueError, OverflowError):
                pass
        return None

    @classmethod
    def _event_time(cls, event):
        if not isinstance(event, dict):
            return None
        for key in ("startTimestamp", "timestamp", "date"):
            n = cls._timestamp(event.get(key))
            if n is not None:
                return n
        return None

    @classmethod
    def _valid_event(cls, x):
        return isinstance(x, dict) and not cls._err(x) and bool(cls._name(x.get("homeTeam"))) and bool(cls._name(x.get("awayTeam")))

    @classmethod
    def _has_players(cls, side):
        if not isinstance(side, dict) or not isinstance(side.get("players"), list):
            return False
        for row in side["players"]:
            if not isinstance(row, dict):
                continue
            p = row.get("player") if isinstance(row.get("player"), dict) else row
            if cls._name(p) or p.get("id") is not None:
                return True
        return False

    @classmethod
    def _valid_lineups(cls, x):
        if not isinstance(x, dict) or cls._err(x):
            return False
        h = x.get("home") if isinstance(x.get("home"), dict) else x.get("homeTeam")
        a = x.get("away") if isinstance(x.get("away"), dict) else x.get("awayTeam")
        return cls._has_players(h) and cls._has_players(a)

    @classmethod
    def _has_stat_item(cls, x):
        if isinstance(x, dict):
            items = x.get("statisticsItems")
            if isinstance(items, list) and any(
                isinstance(i, dict) and (i.get("name") or i.get("key")) and
                any(i.get(k) is not None and i.get(k) != "" for k in ("home", "away", "homeValue", "awayValue", "value"))
                for i in items
            ):
                return True
            return any(cls._has_stat_item(v) for k, v in x.items() if k != "statisticsItems")
        if isinstance(x, list):
            return any(cls._has_stat_item(v) for v in x)
        return False

    @classmethod
    def _valid_statistics(cls, x):
        return isinstance(x, dict) and not cls._err(x) and isinstance(x.get("statistics"), list) and bool(x["statistics"]) and cls._has_stat_item(x["statistics"])

    @classmethod
    def _valid_incidents(cls, x):
        return isinstance(x, dict) and not cls._err(x) and isinstance(x.get("incidents", x.get("events")), list)

    @classmethod
    def _competition(cls, x):
        if not isinstance(x, dict):
            return ""
        for key in ("tournament", "competition", "league"):
            item = x.get(key)
            if not isinstance(item, dict):
                continue
            if item.get("name"):
                return cls._norm(item["name"])
            u = item.get("uniqueTournament")
            if isinstance(u, dict) and u.get("name"):
                return cls._norm(u["name"])
        return ""

    @classmethod
    def _same_fixture(cls, event, witness):
        if not isinstance(witness, dict):
            return False
        h, a = cls._norm(cls._name(event.get("homeTeam"))), cls._norm(cls._name(event.get("awayTeam")))
        if not h or not a or h != cls._norm(cls._name(witness.get("homeTeam"))) or a != cls._norm(cls._name(witness.get("awayTeam"))):
            return False
        t1, t2 = cls._event_time(event), cls._event_time(witness)
        if t1 is not None and t2 is not None and abs(t1 - t2) > 36 * 3600:
            return False
        c1, c2 = cls._competition(event), cls._competition(witness)
        return not c1 or not c2 or c1 in c2 or c2 in c1

    @classmethod
    def _matching_sources(cls, event, evidence):
        final = evidence.get("final_results")
        if not isinstance(final, dict) or cls._err(final) or not isinstance(final.get("sources"), list):
            return []
        matched = set()
        for row in final["sources"]:
            if not isinstance(row, dict) or cls._err(row):
                continue
            src = str(row.get("source") or "").strip().casefold()
            if not src or src in {"sofascore", "primary"} or not isinstance(row.get("events"), list):
                continue
            if any(cls._same_fixture(event, witness) for witness in row["events"]):
                matched.add(src)
        return sorted(matched)

    @staticmethod
    def _prob_from_odds(x):
        try:
            n = float(x)
            return None if not math.isfinite(n) or n <= 1 else 1.0 / n
        except (TypeError, ValueError, OverflowError):
            return None

    def qualify(self, fixture, evidence, now=None):
        now_ok = True
        try:
            now = time.time() if now is None else float(now)
            if not math.isfinite(now):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            now, now_ok = time.time(), False
        e = evidence if isinstance(evidence, dict) else {}
        validators = {"event": self._valid_event, "lineups": self._valid_lineups,
                      "statistics": self._valid_statistics, "incidents": self._valid_incidents}
        checks, missing = {}, []
        for key in self.REQUIRED:
            checks[key] = validators[key](e.get(key))
            if not checks[key]:
                missing.append(key)

        retrieved = self._timestamp(e.get("retrieved_at"))
        age = max(0.0, now - retrieved) if retrieved is not None else None
        checks["freshness"] = now_ok and retrieved is not None and retrieved <= now + 30 and age <= self.stale_after
        event = e.get("event") if isinstance(e.get("event"), dict) else {}
        st = event.get("status") if isinstance(event.get("status"), dict) else {}
        st = st.get("type") if isinstance(st.get("type"), dict) else {}
        checks["pre_match_state"] = str(st.get("state") or "").strip().casefold() in self.PREMATCH_STATES
        home, away = self._name(event.get("homeTeam")), self._name(event.get("awayTeam"))
        checks["fixture_identity"] = bool(home and away and self._event_time(event) is not None)

        odds_count = 0
        odds = e.get("odds")
        if isinstance(odds, dict):
            for market in odds.values():
                if not isinstance(market, dict) or self._err(market) or not isinstance(market.get("markets"), list):
                    continue
                for row in market["markets"]:
                    if not isinstance(row, dict) or not isinstance(row.get("choices"), list):
                        continue
                    for choice in row["choices"]:
                        if isinstance(choice, dict) and self._prob_from_odds(choice.get("decimalValue", choice.get("odds"))) is not None:
                            odds_count += 1
        checks["market_data"] = odds_count > 0
        checks["lineup_signal"] = self._valid_lineups(e.get("lineups"))
        checks["statistics_signal"] = self._valid_statistics(e.get("statistics"))
        checks["incidents_schema"] = self._valid_incidents(e.get("incidents"))

        ver = e.get("verification") if isinstance(e.get("verification"), dict) else {}
        diag = e.get("verification_diagnostics") if isinstance(e.get("verification_diagnostics"), dict) else {}
        matched = self._matching_sources(event, e)
        try:
            diag_count = int(diag.get("matched_fixture_source_count", 0))
        except (TypeError, ValueError, OverflowError):
            diag_count = 0
        diag_sources = diag.get("matched_fixture_sources")
        diag_sources = {str(s).strip().casefold() for s in diag_sources if isinstance(s, str) and s.strip()} if isinstance(diag_sources, list) else set()
        checks["external_verification"] = not self._err(ver) and len(matched) >= 2 and diag_count >= 2 and set(matched).issubset(diag_sources)

        trust = e.get("data_trust") if isinstance(e.get("data_trust"), dict) else {}
        trust_state = str(trust.get("state") or "").strip().upper()
        hard = trust.get("hard_blocks") if isinstance(trust.get("hard_blocks"), list) else ["INVALID_TRUST_BLOCKS"]
        consensus = trust.get("consensus") if isinstance(trust.get("consensus"), dict) else {}
        sources = consensus.get("available_sources")
        sources = {str(s).strip().casefold() for s in sources if isinstance(s, str) and s.strip()} if isinstance(sources, list) else set()
        checks["trusted_evidence"] = trust_state == "TRUSTED" and not hard and consensus.get("state") == "PASS" and len(sources) >= 2

        blockers = []
        if not checks["freshness"]: blockers.append("STALE_OR_INVALID_TIMESTAMP")
        if not checks["fixture_identity"]: blockers.append("FIXTURE_IDENTITY_UNCONFIRMED")
        if not checks["pre_match_state"]: blockers.append("MATCH_STATE_UNKNOWN_OR_INELIGIBLE")
        if not checks["market_data"]: blockers.append("NO_RELIABLE_MARKET_DATA")
        if missing: blockers.append("MISSING_OR_INVALID:" + ",".join(missing))
        if not checks["lineup_signal"]: blockers.append("LINEUP_SIGNAL_MISSING_OR_INCOMPLETE")
        if not checks["statistics_signal"]: blockers.append("STATISTICS_EVIDENCE_EMPTY_OR_INVALID")
        if not checks["incidents_schema"]: blockers.append("INCIDENTS_EVIDENCE_INVALID")
        if not checks["external_verification"]: blockers.append("FIXTURE_MATCHED_INDEPENDENT_VERIFICATION_INSUFFICIENT")
        if not checks["trusted_evidence"]:
            blockers.append("DATA_TRUST_NOT_TRUSTED:" + (",".join(str(x) for x in hard) if hard else trust_state or "MISSING"))
        score = round(100.0 * sum(v is True for v in checks.values()) / len(checks), 1) if checks else 0.0
        ok = not blockers and score >= 80.0
        return {"fixture": {"id": str(fixture), "home": home, "away": away},
                "state": "QUALIFIED" if ok else "NO_BET", "integrity_score": score,
                "freshness_age_seconds": age, "checks": checks, "blockers": blockers,
                "market_observations": odds_count, "matched_verification_sources": matched,
                "data_trust_state": trust_state or "MISSING", "generated_at": now}
