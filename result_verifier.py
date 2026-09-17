import re
import time


class ResultVerifierAgent:
    """Independent result verifier and full-market settlement engine."""

    FINAL = {"post", "final", "finished", "completed"}
    VOID = {"cancelled", "canceled", "postponed", "abandoned", "suspended"}

    @staticmethod
    def _score(payload):
        status = payload.get("status") or {}
        stype = status.get("type") or {}
        state = str(stype.get("state", "")).lower()
        if state in ResultVerifierAgent.VOID or (state not in ResultVerifierAgent.FINAL and not stype.get("completed")):
            return None
        try:
            h = int(float((payload.get("homeTeam") or {}).get("score")))
            a = int(float((payload.get("awayTeam") or {}).get("score")))
        except (TypeError, ValueError):
            return None
        return {"home": h, "away": a, "result": "HOME" if h > a else "AWAY" if h < a else "DRAW"}

    @staticmethod
    def normalize_market(market, selection=""):
        m = re.sub(r"[^a-z0-9]+", " ", str(market or "").lower()).strip()
        s = str(selection or "").lower()
        if "btts" in m or "both teams" in m or s in {"gg", "ng"}: return "btts"
        if "correct" in m and "score" in m: return "correct_score"
        if "double" in m: return "double_chance"
        if "draw no bet" in m or m == "dnb": return "dnb"
        if "handicap" in m: return "handicap"
        if any(x in m for x in ("over", "under", "total goals", "goals ou")): return "goals_ou"
        if "team goals" in m or "team total" in m: return "team_goals"
        if "clean sheet" in m: return "clean_sheet"
        if "corners" in m: return "corners"
        if "cards" in m or "booking" in m: return "cards"
        if "half time" in m or m in {"ht", "ht result"}: return "ht_result"
        if "half time full time" in m or "ht ft" in m: return "ht_ft"
        if "winner" in m or m in {"1x2", "moneyline", "match result"}: return "1x2"
        return m or "unknown"

    @staticmethod
    def line(selection):
        match = re.search(r"([+-]?\d+(?:\.\d+)?)", str(selection or ""))
        return float(match.group(1)) if match else None

    @classmethod
    def settle(cls, row, result, period="ft"):
        market = cls.normalize_market(row.get("market"), row.get("selection"))
        s = str(row.get("selection") or "").lower().strip()
        h, a = result["home"], result["away"]
        total = h + a
        if market == "1x2":
            return 1.0 if (s in {"1", "home", "home win"} and h > a) or (s in {"x", "draw"} and h == a) or (s in {"2", "away", "away win"} and a > h) else 0.0 if s in {"1", "home", "home win", "x", "draw", "2", "away", "away win"} else None
        if market == "double_chance":
            if "1x" in s or "home or draw" in s: return float(h >= a)
            if "x2" in s or "draw or away" in s: return float(a >= h)
            if "12" in s or "home or away" in s: return float(h != a)
        if market == "btts":
            yes = h > 0 and a > 0
            if s in {"yes", "gg", "btts yes"}: return float(yes)
            if s in {"no", "ng", "btts no"}: return float(not yes)
        if market == "goals_ou":
            line = cls.line(s)
            if line is None: return None
            if "over" in s or s.startswith("o"): return 1.0 if total > line else 0.0 if total < line else 0.5
            if "under" in s or s.startswith("u"): return 1.0 if total < line else 0.0 if total > line else 0.5
        if market == "team_goals":
            line = cls.line(s)
            if line is None: return None
            value = h if "home" in s or "1" in s else a if "away" in s or "2" in s else None
            if value is None: return None
            if "over" in s or s.startswith("o"): return 1.0 if value > line else 0.0 if value < line else 0.5
            if "under" in s or s.startswith("u"): return 1.0 if value < line else 0.0 if value > line else 0.5
        if market in {"handicap", "dnb"}:
            if market == "dnb" and h == a: return None
            line = cls.line(s) or 0.0
            margin = h - a if ("home" in s or s.startswith("1")) else a - h
            adjusted = margin + line
            return 1.0 if adjusted > 0 else 0.0 if adjusted < 0 else 0.5
        if market == "clean_sheet":
            home = "home" in s or s.startswith("1")
            clean = a == 0 if home else h == 0 if "away" in s or s.startswith("2") else None
            if clean is None: return None
            if "no" in s: clean = not clean
            return float(clean)
        if market == "correct_score":
            match = re.search(r"(\d+)\s*[-:]\s*(\d+)", s)
            return float(h == int(match.group(1)) and a == int(match.group(2))) if match else None
        return None

    @classmethod
    def verify_consensus(cls, payloads, required=2):
        scores = [cls._score(p) for p in payloads]
        scores = [x for x in scores if x is not None]
        if not scores: return {"status": "UNRESOLVED", "reason": "no independent final results"}
        keys = {(x["home"], x["away"]) for x in scores}
        if len(keys) > 1: return {"status": "CONFLICT", "results": scores}
        return {"status": "VERIFIED" if len(scores) >= required else "SINGLE_SOURCE", "result": scores[0], "sources": len(scores)}
