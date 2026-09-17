import logging
import time

logger = logging.getLogger("emm.learning")


class ClosedLoopLearning:
    """Resolve recorded predictions from cached final scores and evaluate them."""

    RESULT_MAP = {"home": "HOME", "1": "HOME", "away": "AWAY", "2": "AWAY", "draw": "DRAW", "x": "DRAW"}

    def __init__(self, store, evolution):
        self.store = store
        self.evolution = evolution

    @staticmethod
    def _team_result(event):
        status = event.get("status") or {}
        state = str(status.get("type", {}).get("state", "")).lower()
        if state not in {"post", "final"}:
            return None
        home, away = event.get("homeTeam") or {}, event.get("awayTeam") or {}
        try:
            hs, aws = int(home.get("score")), int(away.get("score"))
        except (TypeError, ValueError):
            return None
        return "HOME" if hs > aws else "AWAY" if hs < aws else "DRAW"

    @classmethod
    def _market_outcome(cls, row, result):
        market = str(row.get("market", "")).lower().replace("_", " ")
        selection = str(row.get("selection") or "").lower().strip()
        if market in {"1x2", "match winner", "winner"}:
            mapped = cls.RESULT_MAP.get(selection)
            return None if mapped is None else float(mapped == result)
        if market in {"double chance", "dc"}:
            if selection in {"1x", "home or draw"}: return float(result in {"HOME", "DRAW"})
            if selection in {"x2", "draw or away"}: return float(result in {"DRAW", "AWAY"})
            if selection in {"12", "home or away"}: return float(result in {"HOME", "AWAY"})
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
        logger.info("LEARNING_CYCLE reason=%s resolved=%s unresolved=%s samples=%s status=%s", reason, resolution["resolved"], resolution["unresolved"], evolution["baseline"]["samples"], evolution["status"])
        return {"created_at": time.time(), "resolution": resolution, "evolution": evolution}
