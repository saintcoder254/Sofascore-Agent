"""Historical failure-learning gate for Elite MatchMaster OMEGA.

Forces every candidate bet through documented failure patterns before Final Arbiter approval.
This module is deterministic and evidence-driven; it never invents missing data.
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
    QUESTIONS = [
        ("F1","favorite_short_price_trap","Is this a strong favorite or short-priced 1X/1/2 selection with unresolved draw/upset risk?"),
        ("F2","confidence_inflation","Is the stated confidence materially stronger than the independent evidence supports?"),
        ("F3","probability_value_confusion","Is the selection merely the most likely outcome rather than a positive-EV price?"),
        ("F4","double_counting","Are form, league position, Elo, recent results, or market price being counted more than once?"),
        ("F5","recent_form_overweight","Would the pick fail if the latest 3-5 matches were downweighted?"),
        ("F6","h2h_overweight","Is H2H carrying more weight than its sample size, age, venue, or squad relevance justifies?"),
        ("F7","lineup_uncertainty","Are lineups, injuries, suspensions, or rotation materially unknown?"),
        ("F8","market_movement_ignored","Does the market disagree with the model, or has meaningful price movement not been explained?"),
        ("F9","forced_bet","Would NO BET be correct if this fixture were not already on a betting slip?"),
        ("F10","empirical_engine_artifact","Does an empirical/resampling model conflict with independent Poisson/DC or show a structural artifact?"),
        ("F11","monte_carlo_overconfidence","Is Monte Carlo being treated as proof instead of a conditional simulation?"),
        ("F12","calibration_failure","Does historical calibration justify the claimed probability/confidence band?"),
    ]

    def evaluate(self, candidate: Dict[str, Any], evidence: Dict[str, Any] | None = None) -> Dict[str, Any]:
        evidence = evidence or {}
        market = str(candidate.get("market") or "").upper()
        selection = str(candidate.get("selection") or "").upper()
        odds = self._num(candidate.get("odds"))
        model_p = self._num(candidate.get("model_probability"))
        edge = self._num(candidate.get("edge"))
        blockers, warnings, matched = [], [], []
        if market in {"1X2","DOUBLE_CHANCE","DNB"} and selection in {"HOME","1","1X"}:
            if odds is not None and odds < 1.70:
                matched.append("F1"); blockers.append("F1_FAVORITE_SHORT_PRICE_TRAP")
            elif odds is not None and odds < 2.00:
                matched.append("F1"); warnings.append("F1_FAVORITE_PRICE_REQUIRES_UPSET_DRAW_CHALLENGE")
        if model_p is not None and model_p >= 0.70:
            independent = self._num(evidence.get("independent_probability"))
            if independent is not None and abs(model_p-independent) >= 0.10:
                matched.append("F2"); blockers.append("F2_CONFIDENCE_INFLATION")
            elif evidence.get("confidence_evidence") != "strong":
                matched.append("F2"); warnings.append("F2_HIGH_CONFIDENCE_NEEDS_STRONG_INDEPENDENT_SUPPORT")
        if odds and model_p is not None:
            ev = model_p * odds - 1.0
            if ev <= 0:
                matched.append("F3"); blockers.append("F3_NO_POSITIVE_VALUE")
            if edge is not None and edge <= 0:
                warnings.append("F3_MODEL_DOES_NOT_CLEAR_VALUE_GATE")
        if evidence.get("double_counting_risk"):
            matched.append("F4"); blockers.append("F4_DOUBLE_COUNTING_RISK")
        if evidence.get("recent_form_sensitive"):
            matched.append("F5"); warnings.append("F5_RECENT_FORM_SENSITIVITY")
        if evidence.get("h2h_dominant"):
            matched.append("F6"); warnings.append("F6_H2H_DOMINANT")
        if evidence.get("lineup_unknown"):
            matched.append("F7"); warnings.append("F7_LINEUP_UNCERTAINTY")
        if evidence.get("market_disagreement"):
            matched.append("F8"); warnings.append("F8_MARKET_DISAGREEMENT_UNEXPLAINED")
        if evidence.get("empirical_artifact"):
            matched.append("F10"); blockers.append("F10_EMPIRICAL_ENGINE_ARTIFACT")
        if evidence.get("mc_used_as_validation"):
            matched.append("F11"); blockers.append("F11_MONTE_CARLO_OVERCONFIDENCE")
        if evidence.get("calibration_insufficient"):
            matched.append("F12"); warnings.append("F12_CALIBRATION_INSUFFICIENT")
        if not evidence.get("selection_justification"):
            matched.append("F9"); blockers.append("F9_SELECTION_JUSTIFICATION_MISSING")
        questions = [{"id":c,"archetype":n,"question":q,"triggered":c in matched} for c,n,q in self.QUESTIONS]
        score = max(0.0, 1.0 - 0.12*len(blockers) - 0.04*len(warnings))
        state = "BLOCK" if blockers else ("CAUTION" if warnings else "PASS")
        return asdict(FailureGateResult(state,round(score,4),blockers,warnings,matched,questions))

    @staticmethod
    def _num(value: Any):
        try: return float(value)
        except (TypeError,ValueError): return None
