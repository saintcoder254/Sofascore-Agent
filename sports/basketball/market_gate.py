from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt
from typing import Optional


@dataclass(frozen=True)
class TotalGateResult:
    adjusted_probability: float
    robust_probability: float
    edge: Optional[float]
    line_sensitivity: float
    passed: bool
    reasons: tuple[str, ...]


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def normal_tail_probability(mean: float, sd: float, line: float, side: str) -> float:
    """Return P(total > line) or P(total < line) under a normal approximation."""
    sd = max(sd, 1e-6)
    z = (line - mean) / sd
    if side == "over":
        return 1.0 - _normal_cdf(z)
    if side == "under":
        return _normal_cdf(z)
    raise ValueError("side must be 'over' or 'under'")


def total_gate(
    *,
    side: str,
    line: float,
    projection_total: float,
    uncertainty: float,
    market_probability: Optional[float],
    data_quality: float,
    regime: str,
    team_projection: Optional[float] = None,
    opponent_projection: Optional[float] = None,
    league_avg_team_points: float = 113.0,
    min_edge: float = 0.055,
    low_line_over_threshold: float = 160.0,
    low_line_over_penalty: float = 0.025,
    opponent_floor_ratio: float = 0.90,
    sensitivity_step: float = 2.5,
) -> TotalGateResult:
    """Apply market-specific risk gates before a total-market bet is admitted.

    The gate deliberately separates raw model probability from decision probability.
    Low-line overs, weak opponent scoring floors, high-variance regimes, and fragile
    line edges are penalized rather than silently treated as equivalent to stable edges.
    """
    if side not in {"over", "under"}:
        raise ValueError("side must be 'over' or 'under'")

    sd = max(1.0, uncertainty)
    raw = normal_tail_probability(projection_total, sd, line, side)
    adjusted = raw
    reasons: list[str] = []

    if side == "over" and line <= low_line_over_threshold:
        adjusted -= low_line_over_penalty
        reasons.append("low_line_over_penalty")

    if side == "over" and opponent_projection is not None:
        floor = league_avg_team_points * opponent_floor_ratio
        if opponent_projection < floor:
            adjusted -= 0.035
            reasons.append("opponent_offensive_floor_warning")

    if regime in {"injury_high_variance", "high_variance"}:
        adjusted -= 0.020
        reasons.append("high_variance_penalty")

    adjusted = max(0.001, min(0.999, adjusted))

    # Robustness test: move the line against the selected side by one standard
    # market increment. A fragile edge should not pass simply because the posted
    # line sits at a narrow threshold.
    adverse_line = line + sensitivity_step if side == "over" else line - sensitivity_step
    robust = normal_tail_probability(projection_total, sd, adverse_line, side)
    robust = max(0.001, min(0.999, robust))

    edge = None if market_probability is None else adjusted - market_probability
    robust_edge = None if market_probability is None else robust - market_probability
    sensitivity = adjusted - robust

    if data_quality < 0.70:
        reasons.append("insufficient_data_quality")
    if sensitivity > 0.085:
        reasons.append("line_fragility")
    if edge is None:
        reasons.append("no_market_price")
    elif edge < min_edge:
        reasons.append("edge_below_threshold")
    if robust_edge is not None and robust_edge < min_edge:
        reasons.append("robust_edge_below_threshold")

    passed = (
        data_quality >= 0.70
        and edge is not None
        and edge >= min_edge
        and robust_edge is not None
        and robust_edge >= min_edge
        and sensitivity <= 0.085
    )

    return TotalGateResult(
        adjusted_probability=adjusted,
        robust_probability=robust,
        edge=edge,
        line_sensitivity=sensitivity,
        passed=passed,
        reasons=tuple(dict.fromkeys(reasons)),
    )
