import math, time

class UMIOSQualifier:
    """
    Conservative pre-analysis gate. It never manufactures probabilities.
    A fixture becomes QUALIFIED only when evidence integrity and market
    information pass minimum gates; otherwise the correct state is NO_BET.
    """
    REQUIRED = ("event", "lineups", "statistics", "incidents")

    def __init__(self, stale_after=180):
        self.stale_after = stale_after

    @staticmethod
    def _err(x):
        return isinstance(x, dict) and bool(x.get("error"))

    @staticmethod
    def _prob_from_odds(odds):
        try:
            o=float(odds)
            return None if o <= 1 else 1.0/o
        except (TypeError, ValueError):
            return None

    def qualify(self, fixture, evidence, now=None):
        now = now or time.time()
        checks = {}
        missing = []
        for key in self.REQUIRED:
            ok = key in evidence and not self._err(evidence[key])
            checks[key] = ok
            if not ok:
                missing.append(key)

        retrieved = evidence.get("retrieved_at")
        age = None if retrieved is None else max(0.0, now-float(retrieved))
        checks["freshness"] = age is not None and age <= self.stale_after

        event = evidence.get("event") or {}
        status = ((event.get("status") or {}).get("type") or {})
        state = str(status.get("state") or "").lower()
        checks["pre_match_state"] = state not in {"cancelled","canceled","postponed","abandoned","suspended","finished","completed","final"}

        home = ((event.get("homeTeam") or {}).get("name"))
        away = ((event.get("awayTeam") or {}).get("name"))
        checks["fixture_identity"] = bool(home and away)

        odds_count = 0
        odds_values = []
        for market in (evidence.get("odds") or {}).values():
            if not isinstance(market, dict): continue
            for row in market.get("markets", []) or []:
                for choice in row.get("choices", []) or []:
                    p = self._prob_from_odds(choice.get("fractionalValue") or choice.get("decimalValue") or choice.get("odds"))
                    if p is not None:
                        odds_count += 1
                        odds_values.append(p)
        checks["market_data"] = odds_count > 0

        lineup = evidence.get("lineups") or {}
        checks["lineup_signal"] = bool(lineup.get("home") or lineup.get("away") or lineup.get("homeTeam") or lineup.get("awayTeam"))

        verification = evidence.get("verification") or {}
        checks["external_verification"] = bool(verification.get("events"))

        passed = sum(bool(v) for v in checks.values())
        total = len(checks)
        integrity_score = round(100.0*passed/total, 1) if total else 0.0

        blockers = []
        if not checks["freshness"]: blockers.append("STALE_FEED")
        if not checks["fixture_identity"]: blockers.append("FIXTURE_IDENTITY_UNCONFIRMED")
        if not checks["pre_match_state"]: blockers.append("MATCH_NOT_ELIGIBLE")
        if not checks["market_data"]: blockers.append("NO_RELIABLE_MARKET_DATA")
        if missing: blockers.append("MISSING:" + ",".join(missing))

        # This is an eligibility gate, not a betting confidence score.
        qualified = not blockers and integrity_score >= 80.0
        return {
            "fixture": {"id": str(fixture), "home": home, "away": away},
            "state": "QUALIFIED" if qualified else "NO_BET",
            "integrity_score": integrity_score,
            "freshness_age_seconds": age,
            "checks": checks,
            "blockers": blockers,
            "market_observations": odds_count,
            "generated_at": now,
        }
