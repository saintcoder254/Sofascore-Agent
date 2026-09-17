import logging
import math
import time

logger = logging.getLogger("emm.learning")


class ClosedLoopLearning:
    """Settle predictions from verified final scores and feed results into evolution."""

    RESULT_MAP = {"home": "HOME", "1": "HOME", "away": "AWAY", "2": "AWAY", "draw": "DRAW", "x": "DRAW"}

    def __init__(self, store, evolution):
        self.store = store
        self.evolution = evolution

    @staticmethod
    def _team_result(event):
        status = event.get("status") or {}
        state = str(status.get("type", {}).get("state", "")).lower()
        completed = state in {"post", "final", "finished", "completed"}
        if not completed:
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
            value = features.get(key)
            if cls._num(value) is not None:
                return cls._num(value)
        import re
        match = re.search(r"([+-]?\d+(?:\.\d+)?)", selection)
        return cls._num(match.group(1)) if match else None

    @classmethod
    def _market_outcome(cls, row, result):
        market = str(row.get("market", "")).lower().replace("_", " ").strip()
        selection = str(row.get("selection") or "").lower().strip()
        h, a = result["home"], result["away"]
        total = h + a
        team = "home" if any(x in selection for x in ("home", "1", "host")) and "away" not in selection else "away" if any(x in selection for x in ("away", "2")) else None

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
                return float(total > line)
            if "under" in selection or selection.startswith("u"):
                return float(total < line)
        if market in {"team goals", "team total", "home goals", "away goals"}:
            line = cls._line(row, selection)
            if line is None: return None
            value = h if market == "home goals" or team == "home" else a
            if "over" in selection or selection.startswith("o"): return float(value > line)
            if "under" in selection or selection.startswith("u"): return float(value < line)
        if market in {"clean sheet", "clean sheets"}:
            target_home = team == "home" or "home" in selection
            value = a == 0 if target_home else h == 0 if team == "away" or "away" in selection else None
            if value is None: return None
            return float(value) if "yes" in selection or "clean" in selection and "no" not in selection else float(not value)
        if market in {"correct score", "correctscore"}:
            import re
            match = re.search(r"(\d+)\s*[-:]\s*(\d+)", selection)
            if match: return float(h == int(match.group(1)) and a == int(match.group(2)))
        if market in {"handicap", "asian handicap", "european handicap"}:
            line = cls._line(row, selection)
            if line is None or team is None: return None
            margin = h - a if team == "home" else a - h
            adjusted = margin + line
            if "home" in selection or selection in {"1"}: return float(adjusted > 0)
            if "away" in selection or selection in {"2"}: return float(adjusted > 0)
        return None

    def resolve_finished(self):
        resolved = 0
        unresolved = 0
        for row in self.store.pending_predictions():
            fixture = self.store.get_current(str(row["fixture_id"]))
            if not fixture:
                unresolved += 1
                continue
            result = self._team_result(fixture["payload"])
            outcome = self._market_outcome(row, result) if result else None
            if outcome is None:
                unresolved += 1
                continue
            self.store.record_outcome(row["prediction_id"], outcome, time.time())
            resolved += 1
        return {"resolved": resolved, "unresolved": unresolved}

    def run(self, reason="scheduled"):
        resolution = self.resolve_finished()
        evolution = self.evolution.run_cycle(reason=reason)
        performance = self.store.performance_summary()
        logger.info("LEARNING_CYCLE reason=%s resolved=%s unresolved=%s samples=%s status=%s roi=%s", resolution["resolved"], resolution["unresolved"], evolution["baseline"]["samples"], evolution["status"], performance.get("roi"))
        return {"created_at": time.time(), "resolution": resolution, "evolution": evolution, "performance": performance}
