from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .simulation import SimulationResult

@dataclass(frozen=True)
class MarketProbabilities:
    home_moneyline: float
    away_moneyline: float
    over: Optional[float]
    under: Optional[float]
    home_spread_cover: Optional[float]
    away_spread_cover: Optional[float]

def derive_markets(sim: SimulationResult) -> MarketProbabilities:
    return MarketProbabilities(
        home_moneyline=sim.home_win_probability,
        away_moneyline=1.0 - sim.home_win_probability,
        over=sim.over_probability,
        under=sim.under_probability,
        home_spread_cover=sim.spread_cover_probability,
        away_spread_cover=None if sim.spread_cover_probability is None else 1.0 - sim.spread_cover_probability,
    )
