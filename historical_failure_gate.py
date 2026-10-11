"""Historical failure-learning gate for Elite MatchMaster OMEGA.

Fail-closed, deterministic checks for common prediction failure modes.
Missing price/probability/justification is not silently treated as safe.
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class FailureGateResult:
    state: str
    score: float
    blockers: List[str]
    warnings: List[str]
    matched_archetypes: List[str]
    questions: List[Dict[str, Any]]


class HistoricalFailureGate:
    VERSION = "OMEGA-HISTORICAL-FAILURE-GATE-v2.0"
    QUESTIONS = [
        ("F1", "favorite_short_price_trap", "Is a short-priced favorite exposed to draw/upset risk?"),
        ("F2", "confidence_inflation", "Does the probability materially exceed independent evidence?"),
        ("F3", "probability_value_confusion", "Is this merely likely, or genuinely positive value at this price?"),
        ("F4", "double_counting", "Are correlated inputs counted more than once?"),
        ("F5", "recent_form_overweight", "Does the pick survive down-weighting the last 3-5 matches?"),
        ("F6", "h2h_overweight", "Is H2H overweighted relative to age, venue, sample and squad relevance?"),
        ("F7", "lineup_uncertainty", "Are lineups, injuries, suspensions or rotation materially unknown?"),
        ("F8", "market_movement_ignored", "Is market disagreement or movement explained with timestamped evidence?"),
        ("F9", "forced_bet", "Would NO BET still be considered if this match were not on a slip?"),
        ("F10", "empirical_engine_artifact", "Do independent models conflict or expose resampling artifacts?"),
        ("F11", "monte_carlo_overconfidence", "Is Monte Carlo incorrectly treated as proof rather than conditional sampling?"),
        ("F12", "calibration_failure", "Does out-of-sample calibration support this probability band?"),
    ]

    def evaluate(self, candidate: Dict[str, Any], evidence: Dict[str, Any] | None = None) -> Dict[str, Any]:
        evidence = evidence or {}
        market = str(candidate.get("market") or "").upper().strip()
        selection = str(candidate.get("selection") or "").upper().strip()
        odds = self._num(candidate.get("odds"))
        model_p = self._num(candidate.get("model_probability"))
        supplied_edge = self._num(candidate.get("edge"))
        blockers: List[str] = []
        warnings: List[str] = []
        matched: List[str] = []

        def block(code: str, archetype: str | None = None) -> None:
            blockers.append(code)
            if archetype and archetype not in matched:
                matched.append(archetype)

        def warn(code: str, archetype: str | None = None) -> None:
            warnings.append(code)
            if archetype and archetype not in matched:
                matched.append(archetype)

        if not market or not selection:
            block("F0_MARKET_OR_SELECTION_MISSING")
        if model_p is None:
            block("F0_MODEL_PROBABILITY_MISSING")
        elif not 0.0 <= model_p <= 1.0:
            block("F0_MODEL_PROBABILITY_OUT_OF_RANGE")
        if odds is None or odds <= 1.0:
            block("F0_INVALID_OR_MISSING_ODDS")

        implied = (1.0 / odds) if odds is not None and odds > 1.0 else None
        derived_edge = (model_p - implied) if model_p is not None and implied is not None else None
        ev = (model_p * odds - 1.0) if model_p is not None and odds is not None and odds > 1.0 else None
        if ev is not None and ev <= 0:
            block("F3_NO_POSITIVE_VALUE", "F3")
        if supplied_edge is not None and derived_edge is not None and abs(supplied_edge - derived_edge) > 0.03:
            block("F3_EDGE_FIELD_CONFLICTS_WITH_PROBABILITY_AND_PRICE", "F3")
        if derived_edge is not None and derived_edge <= 0:
            if "F3_NO_POSITIVE_VALUE" not in blockers:
                block("F3_NON_POSITIVE_PRICE_EDGE", "F3")

        if market in {"1X2", "DOUBLE_CHANCE", "DNB"} and selection in {"HOME", "1", "1X"}:
            if odds is not None and odds < 1.70:
                block("F1_FAVORITE_SHORT_PRICE_TRAP", "F1")
            elif odds is not None and odds < 2.00:
                warn("F1_FAVORITE_PRICE_REQUIRES_UPSET_DRAW_CHALLENGE", "F1")

        if model_p is not None and model_p >= 0.70:
            independent = self._num(evidence.get("independent_probability"))
            if independent is not None and abs(model_p - independent) >= 0.10:
                block("F2_CONFIDENCE_INFLATION", "F2")
            elif evidence.get("confidence_evidence") != "strong":
                warn("F2_HIGH_CONFIDENCE_NEEDS_STRONG_INDEPENDENT_SUPPORT", "F2")

        if evidence.get("double_counting_risk"):
            block("F4_DOUBLE_COUNTING_RISK", "F4")
        if evidence.get("recent_form_sensitive"):
            warn("F5_RECENT_FORM_SENSITIVITY", "F5")
        if evidence.get("h2h_dominant"):
            warn("F6_H2H_DOMINANT", "F6")
        if evidence.get("lineup_unknown"):
            warn("F7_LINEUP_UNCERTAINTY", "F7")
        if evidence.get("market_disagreement"):
            block("F8_MARKET_DISAGREEMENT_UNEXPLAINED", "F8")
        if evidence.get("empirical_artifact"):
            block("F10_EMPIRICAL_ENGINE_ARTIFACT", "F10")
        if evidence.get("mc_used_as_validation"):
            block("F11_MONTE_CARLO_OVERCONFIDENCE", "F11")
        if evidence.get("calibration_insufficient"):
            warn("F12_CALIBRATION_INSUFFICIENT", "F12")
        if evidence.get("calibration_failed"):
            block("F12_CALIBRATION_FAILED", "F12")
        historical = evidence.get("historical_market_summary") or {}
        if historical.get("diagnostic_ready") is True:
            observed = self._num(historical.get("observed_hit_rate"))
            predicted = self._num(historical.get("mean_predicted_probability"))
            if observed is None or predicted is None:
                block("F12_HISTORICAL_CALIBRATION_DATA_INVALID", "F12")
            elif predicted - observed >= 0.10:
                block("FH_HISTORICAL_UNDERPERFORMANCE", "F12")
        if not str(evidence.get("selection_justification") or "").strip():
            block("F9_SELECTION_JUSTIFICATION_MISSING", "F9")

        # Preserve order while removing duplicate codes from combined upstream evidence.
        blockers = list(dict.fromkeys(blockers))
        warnings = list(dict.fromkeys(warnings))
        questions = [
            {"id": code, "archetype": name, "question": question, "triggered": code in matched}
            for code, name, question in self.QUESTIONS
        ]
        score = max(0.0, 1.0 - 0.12 * len(blockers) - 0.04 * len(warnings))
        state = "BLOCK" if blockers else ("CAUTION" if warnings else "PASS")
        return {
            **asdict(FailureGateResult(state, round(score, 4), blockers, warnings, matched, questions)),
            "version": self.VERSION,
            "valuation": {
                "odds": odds, "model_probability": model_p,
                "market_implied_probability": round(implied, 6) if implied is not None else None,
                "derived_probability_edge": round(derived_edge, 6) if derived_edge is not None else None,
                "expected_value_per_unit": round(ev, 6) if ev is not None else None,
            },
        }

    @staticmethod
    def _num(value: Any):
        try:
            if value is None or isinstance(value, bool):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
