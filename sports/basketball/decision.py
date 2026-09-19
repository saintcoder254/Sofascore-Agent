from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

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

def decide(probability: float, decimal_odds: Optional[float],
           data_quality: float, uncertainty_width: float,
           min_edge: float = .035, min_quality: float = .70,
           max_uncertainty_width: float = .18) -> Decision:
    market = implied_probability(decimal_odds)
    fair = None if probability <= 0 else 1.0 / probability
    edge = None if market is None else probability - market
    if data_quality < min_quality:
        return Decision("NO_BET", probability, fair, market, edge, "insufficient data quality")
    if uncertainty_width > max_uncertainty_width:
        return Decision("NO_BET", probability, fair, market, edge, "uncertainty too wide")
    if edge is None or edge < min_edge:
        return Decision("WATCH", probability, fair, market, edge, "edge below threshold")
    return Decision("BET", probability, fair, market, edge, "edge clears threshold")
