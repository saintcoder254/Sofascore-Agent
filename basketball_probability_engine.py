"""UMIOS TITAN basketball probability engine.

Basketball-specific probability model with two evidence paths:
1) possession x efficiency when box-score inputs support it;
2) score-form fallback when possession inputs are unavailable.

The model never fabricates possessions or efficiencies. It reports which path
was used, keeps Monte Carlo deterministic, and remains subject to the
qualification/final-arbiter gates.
"""
from __future__ import annotations

import math
import random
import re
import statistics
import time
from typing import Any, Dict, List, Optional, Tuple


class BasketballProbabilityEngine:
    VERSION = "UMIOS-BASKETBALL-FUSION-v3.0-POSS-EFF"
    FINISHED = {"post", "final", "finished", "completed", "ended", "after_penalties", "after_extra_time"}

    def __init__(self, simulations=10000):
        self.simulations = max(5000, int(simulations))

    @staticmethod
    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _finished(cls, e):
        st = ((e.get("status") or {}).get("type") or {}) if isinstance(e, dict) else {}
        return str(st.get("state") or "").lower() in cls.FINISHED or st.get("completed") is True

    @classmethod
    def _sport(cls, event, evidence):
        vals = [event.get(k) for k in ("sport", "sportName", "sportSlug", "eventType", "category", "tournamentName")]
        vals += [evidence.get(k) for k in ("sport", "sportName", "sportSlug", "category")]
        s = " ".join(str(x or "") for x in vals).lower()
        return "basketball" if ("basket" in s or "nba" in s or "wnba" in s) else "other"

    @staticmethod
    def _mean(xs):
        return statistics.mean(xs) if xs else None

    @staticmethod
    def _sd(xs, default=12.0):
        if len(xs) >= 2:
            return max(7.0, statistics.stdev(xs))
        return default

    @classmethod
    def _recent_events(cls, evidence, team_id):
        history = evidence.get("history") or {}
        events = []
        for side in ("home", "away"):
            events.extend((history.get(side) or {}).get("events", []) or [])
        out = []
        for e in events:
            if not isinstance(e, dict) or not cls._finished(e):
                continue
            h, a = e.get("homeTeam") or {}, e.get("awayTeam") or {}
            hs = cls._num((e.get("homeScore") or {}).get("current", h.get("score")))
            aw = cls._num((e.get("awayScore") or {}).get("current", a.get("score")))
            if hs is None or aw is None:
                continue
            if str(h.get("id")) == str(team_id) or str(a.get("id")) == str(team_id):
                out.append(e)

        # Home/away feeds can arrive in separate arrays and are not guaranteed
        # to be chronologically aligned. Never let concatenation order masquerade
        # as recency. Prefer explicit event timestamps; retain source order only
        # when no timestamp exists.
        def event_time(e):
            for key in ("startTimestamp", "timestamp", "startTime", "scheduledAt"):
                value = e.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    try:
                        return float(value)
                    except ValueError:
                        pass
            return None

        # Home/away history arrays can contain the same fixture twice. Deduplicate
        # before selecting the most recent observations so one game cannot receive
        # double statistical weight.
        deduped = {}
        for e in out:
            eid = e.get("id") or e.get("eventId")
            if eid is None:
                # Without a provider event ID or timestamp, do not collapse separate
                # games merely because their scores/stats happen to match. Object
                # identity is safe for duplicated references within one evidence bundle.
                eid = "object:" + str(id(e))
            deduped[str(eid)] = e
        out = list(deduped.values())

        if all(event_time(e) is not None for e in out):
            out.sort(key=event_time)

        return out[-10:]

    @classmethod
    def _recent_stats(cls, evidence, team_id):
        scored, conceded = [], []
        for e in cls._recent_events(evidence, team_id):
            h, a = e.get("homeTeam") or {}, e.get("awayTeam") or {}
            hs = cls._num((e.get("homeScore") or {}).get("current"))
            aw = cls._num((e.get("awayScore") or {}).get("current"))
            if hs is None or aw is None:
                continue
            if str(h.get("id")) == str(team_id):
                scored.append(hs)
                conceded.append(aw)
            else:
                scored.append(aw)
                conceded.append(hs)
        return scored[-10:], conceded[-10:]

    @classmethod
    def _stat_number(cls, obj, aliases):
        """Find a numeric stat by normalized key or stat-name/value pair."""
        aliases = {re.sub(r"[^a-z0-9]", "", a.lower()) for a in aliases}

        def walk(x):
            if isinstance(x, dict):
                # Direct key/value representation.
                for k, v in x.items():
                    nk = re.sub(r"[^a-z0-9]", "", str(k).lower())
                    if nk in aliases:
                        if isinstance(v, (int, float)):
                            return float(v)
                        if isinstance(v, str):
                            m = re.search(r"-?\d+(?:\.\d+)?", v)
                            if m:
                                return float(m.group())
                    # SofaScore-like {name: ..., value: ...} rows.
                name = x.get("name") or x.get("statName") or x.get("label") or x.get("title")
                val = x.get("value")
                if name is not None and val is not None:
                    nn = re.sub(r"[^a-z0-9]", "", str(name).lower())
                    if nn in aliases:
                        if isinstance(val, (int, float)):
                            return float(val)
                        m = re.search(r"-?\d+(?:\.\d+)?", str(val))
                        if m:
                            return float(m.group())
                for v in x.values():
                    if isinstance(v, (dict, list)):
                        found = walk(v)
                        if found is not None:
                            return found
            elif isinstance(x, list):
                for v in x:
                    found = walk(v)
                    if found is not None:
                        return found
            return None

        return walk(obj)

    @classmethod
    def _team_stat_payload(cls, event, team_id):
        """Locate a team-specific statistics/box-score object without inventing attribution."""
        candidates = []
        for key in ("statistics", "stats", "teamStats", "boxScore", "boxscore", "statisticsItems"):
            if key in event:
                candidates.append(event[key])
        if not candidates:
            return None

        # Prefer structures that explicitly carry the team id/name.
        def select(x):
            if isinstance(x, dict):
                tid = x.get("teamId") or x.get("id") if "teamId" in x or "id" in x else None
                if tid is not None and str(tid) == str(team_id):
                    return x
                for k, v in x.items():
                    if isinstance(v, (dict, list)):
                        found = select(v)
                        if found is not None:
                            return found
            elif isinstance(x, list):
                for v in x:
                    found = select(v)
                    if found is not None:
                        return found
            return None

        for c in candidates:
            found = select(c)
            if found is not None:
                return found

        # If the payload is explicitly keyed by team id, use that exact key.
        for c in candidates:
            if isinstance(c, dict):
                for k, v in c.items():
                    if str(k) == str(team_id) and isinstance(v, (dict, list)):
                        return v
        return None

    @classmethod
    def _possessions_from_payload(cls, payload):
        if payload is None:
            return None

        direct = cls._stat_number(payload, (
            "possessions", "possession", "possessions per game", "estimated possessions"
        ))
        if direct is not None and 50 <= direct <= 130:
            return direct

        fga = cls._stat_number(payload, ("field goals attempted", "fga", "fg attempted", "fieldgoalattempts"))
        orb = cls._stat_number(payload, ("offensive rebounds", "orb", "off rebounds", "offensiverebounds"))
        tov = cls._stat_number(payload, ("turnovers", "to", "team turnovers"))
        fta = cls._stat_number(payload, ("free throws attempted", "fta", "ft attempted", "freethrowattempts"))
        if None in (fga, orb, tov, fta):
            return None

        poss = fga - orb + tov + 0.44 * fta
        return poss if 50 <= poss <= 130 else None

    @classmethod
    def _efficiency_sample(cls, event, team_id):
        h, a = event.get("homeTeam") or {}, event.get("awayTeam") or {}
        hs = cls._num((event.get("homeScore") or {}).get("current"))
        aw = cls._num((event.get("awayScore") or {}).get("current"))
        if hs is None or aw is None:
            return None
        payload = cls._team_stat_payload(event, team_id)
        poss = cls._possessions_from_payload(payload)
        if poss is None:
            return None
        if str(h.get("id")) == str(team_id):
            points, opponent = hs, aw
        elif str(a.get("id")) == str(team_id):
            points, opponent = aw, hs
        else:
            return None

        opp_id = a.get("id") if str(h.get("id")) == str(team_id) else h.get("id")
        opp_payload = cls._team_stat_payload(event, opp_id)
        opp_poss = cls._possessions_from_payload(opp_payload)
        # A single team's possession estimate is usable for its ORtg, but DRtg
        # requires the opponent's points per possession with explicit opponent data.
        ortg = 100.0 * points / poss
        drtg = (100.0 * opponent / opp_poss) if opp_poss else None
        return {"poss": poss, "ortg": ortg, "drtg": drtg}

    @classmethod
    def _efficiency_history(cls, evidence, team_id):
        samples = []
        for e in cls._recent_events(evidence, team_id):
            sample = cls._efficiency_sample(e, team_id)
            if sample:
                samples.append(sample)
        return samples[-10:]

    @staticmethod
    def _market_and_line(selection):
        s = str(selection or "").upper().strip()
        m = re.search(r"(OVER|UNDER|O|U)\s*([0-9]+(?:\.[05])?)", s)
        if m:
            return ("OVER" if m.group(1) in {"OVER", "O"} else "UNDER", float(m.group(2)))
        return None, None

    @staticmethod
    def _normal_cdf(x, mu, sd):
        return 0.5 * (1 + math.erf((x - mu) / (max(sd, 1e-9) * math.sqrt(2))))

    def _estimate(self, event, evidence):
        home = event.get("homeTeam") or {}
        away = event.get("awayTeam") or {}
        hs, hc = self._recent_stats(evidence, home.get("id"))
        as_, ac = self._recent_stats(evidence, away.get("id"))
        if min(len(hs), len(as_)) < 5:
            return None

        # Primary basketball model: expected possessions x expected efficiency.
        he = self._efficiency_history(evidence, home.get("id"))
        ae = self._efficiency_history(evidence, away.get("id"))
        efficiency_samples = min(len(he), len(ae))
        model_path = "score_form"

        home_attack = self._mean(hs)
        home_def = self._mean(hc)
        away_attack = self._mean(as_)
        away_def = self._mean(ac)
        form_home = 0.58 * home_attack + 0.42 * away_def + 2.0
        form_away = 0.58 * away_attack + 0.42 * home_def

        hp, ap = form_home, form_away
        expected_possessions = None
        expected_ortg = None
        expected_drtg = None

        if efficiency_samples >= 5:
            h_poss = self._mean([x["poss"] for x in he])
            a_poss = self._mean([x["poss"] for x in ae])
            # Opponent pace is informative but receives less weight than the team's own pace.
            expected_possessions = 0.55 * h_poss + 0.45 * a_poss

            h_ortg = self._mean([x["ortg"] for x in he])
            a_ortg = self._mean([x["ortg"] for x in ae])
            h_drtg_values = [x["drtg"] for x in he if x["drtg"] is not None]
            a_drtg_values = [x["drtg"] for x in ae if x["drtg"] is not None]
            h_drtg = self._mean(h_drtg_values)
            a_drtg = self._mean(a_drtg_values)

            if h_drtg is not None and a_drtg is not None:
                # Opponent defense and offense are blended in efficiency space.
                h_eff = 0.60 * h_ortg + 0.40 * a_drtg
                a_eff = 0.60 * a_ortg + 0.40 * h_drtg
                hp_eff = expected_possessions * h_eff / 100.0
                ap_eff = expected_possessions * a_eff / 100.0
                # Small score-form anchor reduces sensitivity to noisy box-score samples.
                hp = 0.75 * hp_eff + 0.25 * form_home
                ap = 0.75 * ap_eff + 0.25 * form_away
                expected_ortg = {"home": h_eff, "away": a_eff}
                expected_drtg = {"home": h_drtg, "away": a_drtg}
                model_path = "possession_efficiency"

        # Pace/possession information from the current evidence can adjust only when
        # explicitly supplied; it is bounded and never inferred from unrelated stats.
        pace_values = []
        for key in ("pace", "possessions", "possessions per game"):
            val = self._stat_number(evidence.get("statistics") or {}, (key,))
            if val is not None and 50 <= val <= 130:
                pace_values.append(val)
        if pace_values and expected_possessions is None:
            factor = max(0.92, min(1.08, self._mean(pace_values) / 100.0))
            hp *= factor
            ap *= factor

        # Empirical scoring variance. Use recent team totals and team score variance.
        totals = [x + y for x, y in zip(hs[-5:], as_[-5:])]
        score_series = hs[-5:] + as_[-5:]
        total_sd = self._sd(totals, 13.0)
        score_sd = self._sd(score_series, 10.0)
        sd_total = max(total_sd, 1.15 * score_sd)
        sd_total = max(9.0, min(28.0, sd_total))

        production_eligible = model_path == "possession_efficiency"

        return {
            "home_points": max(55.0, min(140.0, hp)),
            "away_points": max(55.0, min(140.0, ap)),
            "expected_total": max(100.0, min(280.0, hp + ap)),
            "sd_total": sd_total,
            "rho": 0.18,
            "home_samples": len(hs),
            "away_samples": len(as_),
            "efficiency_samples": efficiency_samples,
            "model_path": model_path,
            "production_eligible": production_eligible,
            "fallback_reason": (
                None
                if production_eligible
                else "INSUFFICIENT_VERIFIED_POSSESSION_EFFICIENCY_HISTORY"
            ),
            "expected_possessions": expected_possessions,
            "expected_ortg": expected_ortg,
            "expected_drtg": expected_drtg,
            "recent_totals": totals[-5:],
            "team_scored": {"home": hs, "away": as_},
            "team_conceded": {"home": hc, "away": ac},
        }

    @classmethod
    def _mc(cls, mu_h, mu_a, sd_total, rho, n, seed):
        rng = random.Random(seed)
        rows = []
        sd_h = max(7.0, sd_total * 0.52)
        sd_a = max(7.0, sd_total * 0.52)
        shared = max(0.0, min(sd_h, sd_a)) * rho
        for _ in range(n):
            z = rng.gauss(0, 1)
            e1 = rng.gauss(0, 1)
            e2 = rng.gauss(0, 1)
            h = max(0.0, mu_h + shared * z + math.sqrt(max(0.0, sd_h * sd_h - shared * shared)) * e1)
            a = max(0.0, mu_a + shared * z + math.sqrt(max(0.0, sd_a * sd_a - shared * shared)) * e2)
            rows.append((h, a, h + a))
        return rows

    def run(self, event, evidence, gate, simulations=None):
        if gate.get("state") != "QUALIFIED":
            return {"state": "NO_BET", "reason": "qualification_gate_blocked", "candidates": []}
        if self._sport(event, evidence) != "basketball":
            return {"state": "NOT_APPLICABLE", "model": self.VERSION}

        est = self._estimate(event, evidence)
        if not est:
            return {"state": "NO_BET", "reason": "basketball_history_insufficient", "candidates": [], "model": self.VERSION}

        n = max(self.simulations, int(simulations or self.simulations))
        rows = self._mc(
            est["home_points"], est["away_points"], est["sd_total"], est["rho"], n,
            seed=f"{event.get('id')}:{est['expected_total']:.4f}:{est['model_path']}"
        )
        totals = [r[2] for r in rows]

        observed = []
        odds = evidence.get("odds") or {}
        for payload in odds.values():
            if not isinstance(payload, dict):
                continue
            for market in payload.get("markets", []) or []:
                name = str(market.get("name") or market.get("marketName") or "").lower()
                if not any(k in name for k in ("total", "over/under", "over under", "points")):
                    continue
                for c in market.get("choices", []) or []:
                    odd = self._num(c.get("decimalValue", c.get("odds")))
                    if odd is None or odd <= 1:
                        continue
                    direction, line = self._market_and_line(c.get("name") or c.get("label"))
                    if direction and line is not None:
                        observed.append((direction, line, odd))

        candidates = []
        for direction, line, odd in observed:
            same = [x for x in observed if x[1] == line]
            z = sum(1 / x[2] for x in same)
            market_p = (1 / odd) / z if z else None
            if market_p is None:
                continue
            if direction == "OVER":
                p = sum(t > line for t in totals) / n
            else:
                p = sum(t < line for t in totals) / n
            edge = p - market_p
            ev = p * odd - 1
            sample = min(est["home_samples"], est["away_samples"])
            confidence = min(1.0, 0.45 + sample / 20.0)
            required_edge = 0.055 + (1 - confidence) * 0.06
            status = "QUALIFIED" if p >= 0.55 and edge >= required_edge and ev >= 0.05 else "REJECTED"
            candidates.append({
                "market": "TOTAL_POINTS",
                "selection": f"{direction} {line:g}",
                "odds": odd,
                "line": line,
                "model_probability": round(p, 4),
                "market_probability": round(market_p, 4),
                "edge": round(edge, 4),
                "expected_value": round(ev, 4),
                "status": status,
                "confidence": round(confidence, 4),
            })

        qualified = sorted(
            (x for x in candidates if x["status"] == "QUALIFIED"),
            key=lambda x: (x["edge"], x["expected_value"]),
            reverse=True,
        )
        # Score-form is retained for diagnostics and shadow forecasting, but it
        # cannot promote a market to QUALIFIED_PREDICTION. Without verified
        # possession/efficiency evidence, recent scoring can be dominated by
        # shooting variance, overtime, matchup noise, or schedule effects.
        selection = qualified[0] if qualified and est["production_eligible"] else None
        if selection:
            selection["tail_risk"] = round(sum(t > selection["line"] for t in totals) / n, 4)

        return {
            "state": "QUALIFIED_PREDICTION" if selection else "NO_BET",
            "model": self.VERSION,
            "simulations": n,
            "expected_points": {"home": round(est["home_points"], 2), "away": round(est["away_points"], 2)},
            "expected_total": round(est["expected_total"], 2),
            "distribution_sd": round(est["sd_total"], 2),
            "model_path": est["model_path"],
            "production_eligible": est["production_eligible"],
            "fallback_reason": est["fallback_reason"],
            "expected_possessions": None if est["expected_possessions"] is None else round(est["expected_possessions"], 3),
            "expected_ortg": est["expected_ortg"],
            "expected_drtg": est["expected_drtg"],
            "history": {
                "home_games": est["home_samples"],
                "away_games": est["away_samples"],
                "minimum_games": min(est["home_samples"], est["away_samples"]),
                "efficiency_games": est["efficiency_samples"],
            },
            "simulated_totals": totals if selection else totals[:2000],
            "candidates": candidates,
            "selection": selection,
            "generated_at": time.time(),
        }
