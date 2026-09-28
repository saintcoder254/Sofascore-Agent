"""
Elite MatchMaster — Basketball Volatility / Tail-Risk Guard
Version: EMM-BVG-1.0

Purpose:
    Prevent an apparently attractive basketball total from passing simply
    because the model mean sits below/above the bookmaker line.

Design principles:
    - Early-season samples are treated as high uncertainty.
    - Recent defensive leakage is a first-class signal.
    - Relevant H2H scoring is a volatility signal, not an automatic pick.
    - Market-line proximity increases uncertainty.
    - Upper-tail probability matters for UNDERS.
    - A NO_BET result is preferred to forced selection.
    - This module is deterministic and evidence-driven; it does not fabricate data.

This is a risk gate, not a prediction engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
import math
import statistics
import time


@dataclass
class RiskAssessment:
    state: str
    score: int
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)
    generated_at: float = field(default_factory=time.time)

    @property
    def passed(self) -> bool:
        return self.state == "PASS"


class BasketballVolatilityGuard:
    """
    Mandatory adversarial gate for basketball totals.

    It does not decide OVER vs UNDER. It decides whether the evidence is
    sufficiently stable for a totals candidate to proceed to the Final Arbiter.
    """

    VERSION = "EMM-BVG-1.0"

    TOTAL_MARKETS = {
        "TOTAL_POINTS",
        "TOTAL",
        "OVER_UNDER",
        "OVER/UNDER",
        "TOTAL_POINTS_OT",
    }

    UNDER_WORDS = {"UNDER", "U", "UNDER_OT", "UNDER_TOTAL"}
    OVER_WORDS = {"OVER", "O", "OVER_OT", "OVER_TOTAL"}

    def __init__(
        self,
        early_sample_limit: int = 5,
        recent_games: int = 5,
        h2h_games: int = 5,
        high_recent_total: float = 175.0,
        extreme_recent_total: float = 185.0,
        line_uncertainty_band: float = 8.0,
        minimum_tail_margin: float = 0.08,
    ):
        self.early_sample_limit = early_sample_limit
        self.recent_games = recent_games
        self.h2h_games = h2h_games
        self.high_recent_total = high_recent_total
        self.extreme_recent_total = extreme_recent_total
        self.line_uncertainty_band = line_uncertainty_band
        self.minimum_tail_margin = minimum_tail_margin

    @staticmethod
    def _num(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip().upper()

    @classmethod
    def _is_basketball(cls, event: Dict[str, Any], prediction: Dict[str, Any]) -> bool:
        haystack = " ".join(
            str(event.get(k, ""))
            for k in (
                "sport",
                "sportName",
                "category",
                "sportSlug",
                "eventType",
                "tournamentName",
            )
        ).upper()
        selection = prediction.get("selection") or {}
        haystack += " " + str(selection.get("market", "")).upper()
        haystack += " " + str(selection.get("selection", "")).upper()
        return "BASKET" in haystack or "NBA" in haystack or "WNBA" in haystack

    @classmethod
    def _market(cls, prediction: Dict[str, Any]) -> str:
        selection = prediction.get("selection") or {}
        return cls._text(selection.get("market"))

    @classmethod
    def _selection(cls, prediction: Dict[str, Any]) -> str:
        selection = prediction.get("selection") or {}
        raw = cls._text(selection.get("selection"))
        if raw.startswith("UNDER"):
            return "UNDER"
        if raw.startswith("OVER"):
            return "OVER"
        return raw

    @classmethod
    def _line(cls, prediction: Dict[str, Any]) -> Optional[float]:
        selection = prediction.get("selection") or {}
        for key in ("line", "threshold", "total"):
            value = cls._num(selection.get(key))
            if value is not None:
                return value

        import re

        raw = str(selection.get("selection") or "")
        match = re.search(r"(?:OVER|UNDER|O|U)\s*([0-9]+(?:\.[0-9]+)?)", raw, re.I)
        if match:
            return float(match.group(1))
        return None

    @classmethod
    def _extract_games(cls, evidence: Dict[str, Any], keys: Iterable[str]) -> List[float]:
        values: List[float] = []

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    normalized = str(key).lower()
                    if any(k in normalized for k in keys):
                        if isinstance(value, (int, float)):
                            values.append(float(value))
                    if isinstance(value, (dict, list)):
                        walk(value)
            elif isinstance(obj, list):
                for value in obj:
                    walk(value)

        walk(evidence)
        return values

    @classmethod
    def _score_history(cls, evidence: Dict[str, Any]) -> List[float]:
        """
        Extract completed-game totals from common historical structures.
        Only accepts explicit home/away scores; it does not infer totals from
        unrelated numeric statistics.
        """
        totals: List[float] = []
        history = evidence.get("history") or {}

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                home = obj.get("homeScore")
                away = obj.get("awayScore")

                if isinstance(home, dict):
                    home = home.get("current", home.get("display"))
                if isinstance(away, dict):
                    away = away.get("current", away.get("display"))

                h = cls._num(home)
                a = cls._num(away)
                if h is not None and a is not None:
                    totals.append(h + a)

                for value in obj.values():
                    if isinstance(value, (dict, list)):
                        walk(value)

            elif isinstance(obj, list):
                for value in obj:
                    walk(value)

        walk(history)
        return totals

    @classmethod
    def _explicit_h2h_totals(cls, evidence: Dict[str, Any]) -> List[float]:
        h2h = evidence.get("h2h") or evidence.get("head_to_head") or {}
        temp = {"history": h2h}
        return cls._score_history(temp)

    @staticmethod
    def _above(values: List[float], threshold: float) -> float:
        if not values:
            return 0.0
        return sum(v > threshold for v in values) / len(values)

    @staticmethod
    def _under_probability_from_simulations(
        simulations: Iterable[float], line: float
    ) -> Optional[float]:
        sims = [float(x) for x in simulations if isinstance(x, (int, float))]
        if not sims:
            return None
        return sum(x < line for x in sims) / len(sims)

    def evaluate(
        self,
        event: Dict[str, Any],
        evidence: Dict[str, Any],
        prediction: Dict[str, Any],
    ) -> RiskAssessment:
        # Football and non-total markets are outside this guard.
        if not self._is_basketball(event, prediction):
            return RiskAssessment(
                state="PASS",
                score=0,
                signals={"applicable": False},
            )

        market = self._market(prediction)
        if market not in self.TOTAL_MARKETS:
            return RiskAssessment(
                state="PASS",
                score=0,
                signals={"applicable": True, "reason": "non_total_market"},
            )

        selection = self._selection(prediction)
        line = self._line(prediction)

        recent = self._score_history(evidence)
        h2h = self._explicit_h2h_totals(evidence)

        # Prefer explicitly supplied team-game count when available.
        hist = prediction.get("history") or {}
        home_games = int(hist.get("home_games") or 0)
        away_games = int(hist.get("away_games") or 0)
        sample = min(home_games, away_games)

        if sample == 0 and recent:
            sample = min(len(recent), self.recent_games)

        blockers: List[str] = []
        warnings: List[str] = []
        signals: Dict[str, Any] = {
            "applicable": True,
            "market": market,
            "selection": selection,
            "line": line,
            "recent_totals_count": len(recent),
            "h2h_totals_count": len(h2h),
            "minimum_team_sample": sample,
        }

        score = 0

        # 1. Small samples are inherently unstable.
        if sample and sample < self.early_sample_limit:
            score += 2
            warnings.append("EARLY_SEASON_THIN_SAMPLE")

        # 2. Recent scoring environment.
        if recent:
            recent_window = recent[-self.recent_games :]
            mean_recent = statistics.mean(recent_window)
            median_recent = statistics.median(recent_window)
            high_rate = self._above(recent_window, self.high_recent_total)
            extreme_rate = self._above(recent_window, self.extreme_recent_total)

            signals.update(
                recent_mean=round(mean_recent, 3),
                recent_median=round(median_recent, 3),
                recent_high_total_rate=round(high_rate, 3),
                recent_extreme_total_rate=round(extreme_rate, 3),
            )

            if mean_recent >= self.high_recent_total:
                score += 2
                warnings.append("ELEVATED_RECENT_SCORING_ENVIRONMENT")

            if extreme_rate >= 0.40:
                score += 2
                warnings.append("FREQUENT_EXTREME_TOTALS")

            # A very high recent environment is particularly dangerous to an Under.
            if selection == "UNDER" and mean_recent >= self.extreme_recent_total:
                blockers.append("UNDER_EXPOSED_TO_RECENT_HIGH_TOTAL_ENVIRONMENT")

        # 3. H2H is a volatility input, not a direction signal.
        if h2h:
            h2h_window = h2h[-self.h2h_games :]
            h2h_mean = statistics.mean(h2h_window)
            h2h_high_rate = self._above(h2h_window, self.high_recent_total)
            signals.update(
                h2h_mean=round(h2h_mean, 3),
                h2h_high_total_rate=round(h2h_high_rate, 3),
            )

            if h2h_high_rate >= 0.50:
                score += 1
                warnings.append("H2H_HIGH_TOTAL_FREQUENCY")

            if selection == "UNDER" and line is not None and h2h_mean >= line + 5:
                score += 2
                blockers.append("H2H_SCORING_ENVIRONMENT_ABOVE_UNDER_LINE")

        # 4. Market-line proximity: being only a few points away from the
        # estimated environment is not enough to justify a confident Under.
        model_probability = self._num(
            (prediction.get("selection") or {}).get("model_probability")
        )
        model_total = self._num(
            prediction.get("model_total")
            or prediction.get("expected_total")
            or (prediction.get("probabilities") or {}).get("expected_total")
        )

        if line is not None and model_total is not None:
            distance = abs(model_total - line)
            signals["model_total"] = round(model_total, 3)
            signals["line_distance"] = round(distance, 3)

            if distance <= self.line_uncertainty_band:
                score += 1
                warnings.append("MODEL_TOTAL_WITHIN_UNCERTAINTY_BAND")

            if selection == "UNDER" and model_total >= line - 2:
                score += 2
                blockers.append("UNDER_MARGIN_TOO_THIN")

        # 5. Tail-risk gate. Prefer explicit simulations if the probability
        # engine supplied them.
        simulations = (
            prediction.get("simulated_totals")
            or prediction.get("monte_carlo_totals")
            or (prediction.get("monte_carlo") or {}).get("totals")
            or []
        )

        if line is not None and simulations:
            under_p = self._under_probability_from_simulations(simulations, line)
            if under_p is not None:
                signals["simulated_under_probability"] = round(under_p, 4)
                if selection == "UNDER" and under_p < 0.60:
                    score += 3
                    blockers.append("MONTE_CARLO_UNDER_PROBABILITY_TOO_LOW")
                elif selection == "UNDER" and under_p < 0.68:
                    score += 1
                    warnings.append("MONTE_CARLO_UNDER_TAIL_NOT_COMFORTABLE")

        # 6. Probability/edge must not rescue an unstable evidence regime.
        edge = self._num((prediction.get("selection") or {}).get("edge"))
        if selection == "UNDER" and edge is not None and edge < 0.06:
            score += 1
            warnings.append("UNDER_EDGE_NOT_LARGE_ENOUGH_FOR_VOLATILITY")

        # Mandatory veto threshold.
        if len(blockers) > 0:
            state = "BLOCK"
        elif score >= 4:
            blockers.append("VOLATILITY_SCORE_EXCEEDED")
            state = "BLOCK"
        else:
            state = "PASS"

        signals["volatility_score"] = score
        signals["risk_gate_version"] = self.VERSION

        return RiskAssessment(
            state=state,
            score=score,
            blockers=blockers,
            warnings=warnings,
            signals=signals,
        )


def evaluate_basketball_candidate(
    event: Dict[str, Any],
    evidence: Dict[str, Any],
    prediction: Dict[str, Any],
) -> Dict[str, Any]:
    """Convenience function used by UMIOS/Final Arbiter integrations."""
    assessment = BasketballVolatilityGuard().evaluate(
        event=event,
        evidence=evidence,
        prediction=prediction,
    )
    return {
        "state": assessment.state,
        "score": assessment.score,
        "blockers": assessment.blockers,
        "warnings": assessment.warnings,
        "signals": assessment.signals,
        "generated_at": assessment.generated_at,
        "version": BasketballVolatilityGuard.VERSION,
    }


if __name__ == "__main__":
    # Reproduces the failure mode from the 28 Sep 2026 ticket without
    # claiming that these numbers constitute a complete historical dataset.
    example_event = {
        "sport": "Basketball",
        "homeTeam": {"name": "Latvijas Universitate"},
        "awayTeam": {"name": "BK Ventspils"},
    }

    example_evidence = {
        "history": [
            {"homeScore": {"current": 66}, "awayScore": {"current": 104}},
            {"homeScore": {"current": 76}, "awayScore": {"current": 98}},
        ],
        "h2h": [
            {"homeScore": {"current": 96}, "awayScore": {"current": 118}},
        ],
    }

    example_prediction = {
        "selection": {
            "market": "TOTAL_POINTS",
            "selection": "UNDER 177.5",
            "model_probability": 0.60,
            "edge": 0.06,
        },
        "history": {
            "home_games": 1,
            "away_games": 1,
        },
        "model_total": 176.0,
    }

    import json
    print(
        json.dumps(
            evaluate_basketball_candidate(
                example_event, example_evidence, example_prediction
            ),
            indent=2,
            sort_keys=True,
        )
    )
