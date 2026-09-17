import logging
import time

logger = logging.getLogger("emm.learning")


class ClosedLoopLearning:
    """Settle predictions only from completed fixtures, with conflict protection."""

    RESULT_MAP = {"home": "HOME", "1": "HOME", "away": "AWAY", "2": "AWAY", "draw": "DRAW", "x": "DRAW"}
    FINAL_STATES = {"post", "final", "finished", "completed"}
    CANCELLED_STATES = {"cancelled", "canceled", "postponed", "abandoned", "suspended"}

    def __init__(self, store, evolution):
        self.store = store
        self.evolution = evolution

    @classmethod
    def _team_result(cls, event):
        status = event.get("status") or {}
        stype = status.get("type") or {}
        state = str(stype.get("state", "")).lower()
        if state in cls.CANCELLED_STATES:
            return None
        if state not in cls.FINAL_STATES and not bool(stype.get("completed")):
            return None
        home, away = event.get("homeTeam") or {}, event.get("awayTeam") or {}
        try:
            hs, aws = int(float(home.get("score"))), int(float(away.get("score")))
        except (TypeError, ValueError):
            return None
        return {"home": hs, "away": aws, "result": "HOME" if hs > aws else "AWAY" if hs < aws else "DRAW"}

    @staticmethod
    def _num(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _line(cls, row, selection):
        features = row.get("features") or {}
        for key in ("line", "threshold", "handicap", "total"):
            value = cls._num(features.get(key))
            if value is not None:
                return value
        import re
        match = re.search(r"([+-]?\d+(?:\.\d+)?)", selection)
        return cls._num(match.group(1)) if match else None

    @classmethod
    def _market_outcome(cls, row, result):
        market = str(row.get("market", "")).lower().replace("_", " ").strip()
        selection = str(row.get("selection") or "").lower().strip()
        h, a = result["home"], result["away"]
        total = h + a
        team = "home" if ("home" in selection or selection in {"1", "home over", "home under"}) and "away" not in selection else "away" if ("away" in selection or selection in {"2", "away over", "away under"}) else None

        if market in {"1x2", "match winner", "winner"}:
            mapped = cls.RESULT_MAP.get(selection)
            return None if mapped is None else float(mapped == result["result"])
        if market in {"double chance", "dc"}:
            if selection in {"1x", "home or draw"}: return float(result["result"] in {"HOME", "DRAW"})
            if selection in {"x2", "draw or away"}: return float(result["result"] in {"DRAW", "AWAY"})
            if selection in {"12", "home or away"}: return float(result["result"] in {"HOME", "AWAY"})
        if market in {"dnb", "draw no bet"}:
            if selection in {"home", "1"}: return 1.0 if result["result"] == "HOME" else 0.0 if result["result"] == "AWAY" else None
            if selection in {"away", "2"}: return 1.0 if result["result"] == "AWAY" else 0.0 if result["result"] == "HOME" else None
        if market in {"btts", "gg", "both teams to score"}:
            yes = h > 0 and a > 0
            if selection in {"yes", "gg", "btts yes"}: return float(yes)
            if selection in {"no", "ng", "btts no"}: return float(not yes)
        if market in {"over under", "o/u", "goals", "total goals", "over/under"}:
            line = cls._line(row, selection)
            if line is None: return None
            if "over" in selection or selection.startswith("o"):
                return 1.0 if total > line else 0.0 if total < line else 0.5
            if "under" in selection or selection.startswith("u"):
                return 1.0 if total < line else 0.0 if total > line else 0.5
        if market in {"team goals", "team total", "home goals", "away goals"}:
            line = cls._line(row, selection)
            if line is None or team is None: return None
            value = h if team == "home" else a
            if "over" in selection or selection.startswith("o"):
                return 1.0 if value > line else 0.0 if value < line else 0.5
            if "under" in selection or selection.startswith("u"):
                return 1.0 if value < line else 0.0 if value > line else 0.5
        if market in {"clean sheet", "clean sheets"}:
            if team == "home" or "home" in selection: clean = a == 0
            elif team == "away" or "away" in selection: clean = h == 0
            else: return None
            if "no" in selection: clean = not clean
            return float(clean)
        if market in {"correct score", "correctscore"}:
            import re
            match = re.search(r"(\d+)\s*[-:]\s*(\d+)", selection)
            return float(h == int(match.group(1)) and a == int(match.group(2))) if match else None
        if market in {"handicap", "asian handicap", "european handicap"}:
            line = cls._line(row, selection)
            if line is None or team is None: return None
            margin = h - a if team == "home" else a - h
            adjusted = margin + line
            return 1.0 if adjusted > 0 else 0.0 if adjusted < 0 else 0.5
        return None

    @staticmethod
    def _has_conflict(payload):
        if payload.get("verification_conflicts"):
            return True
        verification = payload.get("verification") or {}
        return bool(verification.get("conflict"))

    def resolve_finished(self):
        resolved = unresolved = blocked = 0
        for row in self.store.pending_predictions():
            fixture = self.store.get_current(str(row["fixture_id"]))
            if not fixture:
                unresolved += 1
                continue
            payload = fixture["payload"]
            if self._has_conflict(payload):
                blocked += 1
                continue
            result = self._team_result(payload)
            outcome = self._market_outcome(row, result) if result else None
            if outcome is None:
                unresolved += 1
                continue
            self.store.record_outcome(row["prediction_id"], outcome, time.time())
            resolved += 1
        return {"resolved": resolved, "unresolved": unresolved, "blocked_conflicts": blocked}

    def run(self, reason="scheduled"):
        resolution = self.resolve_finished()
        evolution = self.evolution.run_cycle(reason=reason)
        performance = self.store.performance_summary()
        logger.info("LEARNING_CYCLE reason=%s resolved=%s unresolved=%s blocked_conflicts=%s samples=%s status=%s roi=%s", reason, resolution["resolved"], resolution["unresolved"], resolution["blocked_conflicts"], evolution["baseline"]["samples"], evolution["status"], performance.get("roi"))
        return {"created_at": time.time(), "resolution": resolution, "evolution": evolution, "performance": performance}
