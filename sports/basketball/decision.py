from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .market_gate import total_gate


@dataclass
class Decision:
    action: str
    probability: float
    fair_odds: Optional[float]
    market_implied_probability: Optional[float]
    edge: Optional[float]
    reason: str


def implied_probability(decimal_odds: Optional[float]) -> Optional[float]:
    if decimal_odds is None or decimal_odds <= 1:
        return None
    return 1.0 / decimal_odds


def decide(
    probability: float,
    decimal_odds: Optional[float],
    data_quality: float,
    uncertainty_width: float,
    min_edge: float = 0.035,
    min_quality: float = 0.70,
    max_uncertainty_width: float = 0.18,
    *,
    market_type: Optional[str] = None,
    side: Optional[str] = None,
    line: Optional[float] = None,
    projection_total: Optional[float] = None,
    uncertainty: Optional[float] = None,
    regime: str = "neutral",
    team_projection: Optional[float] = None,
    opponent_projection: Optional[float] = None,
    league_avg_team_points: float = 113.0,
) -> Decision:
    """Decision gate with an optional basketball total-market risk layer.

    Existing callers keep the legacy behavior. Total-market callers can activate
    the stricter gate, which separates raw model probability from decision
    probability and rejects fragile edges.
    """
    market = implied_probability(decimal_odds)
    fair = None if probability <= 0 else 1.0 / probability
    edge = None if market is None else probability - market

    if data_quality < min_quality:
        return Decision("NO_BET", probability, fair, market, edge, "insufficient data quality")
    if uncertainty_width > max_uncertainty_width:
        return Decision("NO_BET", probability, fair, market, edge, "uncertainty too wide")

    if market_type == "total" and side in {"over", "under"} and line is not None and projection_total is not None:
        gate = total_gate(
            side=side,
            line=line,
            projection_total=projection_total,
            uncertainty=uncertainty if uncertainty is not None else max(1.0, uncertainty_width * 100.0),
            market_probability=market,
            data_quality=data_quality,
            regime=regime,
            team_projection=team_projection,
            opponent_projection=opponent_projection,
            league_avg_team_points=league_avg_team_points,
            min_edge=max(min_edge, 0.055),
        )
        gate_fair = None if gate.adjusted_probability <= 0 else 1.0 / gate.adjusted_probability
        gate_edge = gate.edge
        if not gate.passed:
            return Decision(
                "NO_BET",
                gate.adjusted_probability,
                gate_fair,
                market,
                gate_edge,
                "total risk gate: " + ", ".join(gate.reasons),
            )
        return Decision(
            "BET",
            gate.adjusted_probability,
            gate_fair,
            market,
            gate_edge,
            "total risk gate passed",
        )

    if edge is None or edge < min_edge:
        return Decision("WATCH", probability, fair, market, edge, "edge below threshold")
    return Decision("BET", probability, fair, market, edge, "edge clears threshold")
