"""Double-chance / draw-no-bet failure gate.

Edges are measured in probability points (model probability minus 1/decimal odds).
Expected value is measured separately as p * odds - 1. Missing stress evidence
fails closed. This gate vetoes; it never creates a selection.
"""
class DoubleChanceFailureGate:
    VERSION = "OMEGA-DC-FAILURE-GATE-v2.0"
    MARKETS = {"DOUBLE_CHANCE", "DNB"}

    def __init__(self, min_p=0.60, min_edge=0.03, min_ev=0.03, max_sensitivity=0.10):
        self.min_p = float(min_p)
        self.min_edge = float(min_edge)
        self.min_ev = float(min_ev)
        self.max_sensitivity = float(max_sensitivity)

    @staticmethod
    def _num(value):
        try:
            if value is None or isinstance(value, bool):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def evaluate(self, candidate, evidence=None):
        evidence = evidence or {}
        market = str(candidate.get("market") or "").upper().strip()
        selection = str(candidate.get("selection") or "").upper().strip()
        if market not in self.MARKETS:
            return {"version": self.VERSION, "state": "NOT_APPLICABLE", "blockers": [], "warnings": []}
        supported = {"X2", "1X", "AWAY", "HOME", "2", "1"}
        if selection not in supported:
            return {"version": self.VERSION, "state": "BLOCK", "blockers": ["DC_UNSUPPORTED_SELECTION"], "warnings": []}

        p = self._num(candidate.get("model_probability"))
        odds = self._num(candidate.get("odds"))
        blockers, warnings = [], []
        if p is None or not 0.0 <= p <= 1.0:
            blockers.append("DC_MISSING_OR_INVALID_PROBABILITY")
        if odds is None or odds <= 1.0:
            blockers.append("DC_MISSING_OR_INVALID_PRICE")

        implied = (1.0 / odds) if odds is not None and odds > 1.0 else None
        edge = (p - implied) if p is not None and implied is not None else None
        ev = (p * odds - 1.0) if p is not None and odds is not None and odds > 1.0 else None
        if p is not None and p < self.min_p:
            blockers.append("DC_PROBABILITY_BELOW_MINIMUM")
        if edge is not None and edge < self.min_edge:
            blockers.append("DC_EDGE_BELOW_MINIMUM")
        if ev is not None and ev < self.min_ev:
            blockers.append("DC_EXPECTED_VALUE_BELOW_MINIMUM")

        stress = evidence.get("double_chance_stress") or {}
        adverse = self._num(stress.get("adverse_branch_probability"))
        if adverse is None or not 0.0 <= adverse <= 1.0:
            blockers.append("DC_ADVERSE_BRANCH_NOT_TESTED")
        elif adverse < 0.20:
            warnings.append("DC_ADVERSE_BRANCH_LOW_PROBABILITY_REVIEW_REQUIRED")

        expected_adverse = "home_win" if selection in {"X2", "AWAY", "2"} else "away_win"
        adverse_market = str(stress.get("adverse_branch_market") or "").lower().strip()
        if adverse_market not in {"home_win", "away_win", "draw"}:
            blockers.append("DC_ADVERSE_BRANCH_INVALID")
        elif adverse_market != expected_adverse:
            blockers.append("DC_ADVERSE_BRANCH_DOES_NOT_MATCH_SELECTION")

        sensitivity = self._num(stress.get("probability_sensitivity"))
        if sensitivity is None:
            blockers.append("DC_SENSITIVITY_NOT_TESTED")
        elif sensitivity < 0 or sensitivity > self.max_sensitivity:
            blockers.append("DC_REGIME_SENSITIVITY_HIGH_OR_INVALID")

        if stress.get("market_confirmed") is not True:
            blockers.append("DC_MARKET_CONFIRMATION_MISSING")

        # Optional cross-model check: large disagreements are blockers, not averages to hide.
        independent_p = self._num(evidence.get("independent_probability"))
        if p is not None and independent_p is not None and abs(p - independent_p) >= 0.10:
            blockers.append("DC_INDEPENDENT_MODEL_DISAGREEMENT")
        if evidence.get("source_conflict"):
            blockers.append("DC_SOURCE_CONFLICT")

        blockers = list(dict.fromkeys(blockers))
        warnings = list(dict.fromkeys(warnings))
        state = "BLOCK" if blockers else ("CAUTION" if warnings else "PASS")
        return {
            "version": self.VERSION, "state": state, "blockers": blockers, "warnings": warnings,
            "inputs": {
                "probability": p, "odds": odds, "market_implied_probability": implied,
                "derived_probability_edge": edge, "expected_value_per_unit": ev,
                "min_probability": self.min_p, "min_edge": self.min_edge, "min_ev": self.min_ev,
                "adverse_branch_probability": adverse, "adverse_branch_market": adverse_market,
                "probability_sensitivity": sensitivity, "market_confirmed": stress.get("market_confirmed"),
            },
        }
