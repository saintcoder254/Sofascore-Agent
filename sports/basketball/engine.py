from __future__ import annotations
from dataclasses import dataclass, field
from math import sqrt
from typing import Dict, Optional

@dataclass
class TeamProfile:
    offensive_rating: float
    defensive_rating: float
    pace: float
    three_rate: float = 0.0
    three_pct: float = 0.0
    turnover_rate: float = 0.0
    offensive_rebound_rate: float = 0.0
    free_throw_rate: float = 0.0

@dataclass
class GameContext:
    home: TeamProfile
    away: TeamProfile
    home_advantage: float = 2.0
    rest_home: float = 1.0
    rest_away: float = 1.0
    data_quality: float = 1.0
    injury_volatility: float = 0.0
    market_total: Optional[float] = None
    market_spread_home: Optional[float] = None
    metadata: Dict[str, object] = field(default_factory=dict)

@dataclass
class Projection:
    possessions: float
    home_points: float
    away_points: float
    total_points: float
    spread_home: float
    uncertainty: float
    regime: str
    data_quality: float

class BasketballEngine:
    VERSION = "basketball-titan-1.0"

    @staticmethod
    def _blend(a: float, b: float, wa: float = 0.5) -> float:
        return wa * a + (1.0 - wa) * b

    @staticmethod
    def _regime(ctx: GameContext, possessions: float) -> str:
        if ctx.injury_volatility >= 0.25:
            return "injury_high_variance"
        if possessions >= 103:
            return "fast_pace"
        if possessions <= 94:
            return "slow_pace"
        return "neutral"

    def project(self, ctx: GameContext) -> Projection:
        possessions = self._blend(ctx.home.pace, ctx.away.pace)
        home_eff = self._blend(ctx.home.offensive_rating, 120.0 - ctx.away.defensive_rating, 0.55)
        away_eff = self._blend(ctx.away.offensive_rating, 120.0 - ctx.home.defensive_rating, 0.55)
        home_eff += ctx.home_advantage + 0.25 * (ctx.rest_home - ctx.rest_away)
        away_eff += 0.25 * (ctx.rest_away - ctx.rest_home)
        home_points = possessions * home_eff / 100.0
        away_points = possessions * away_eff / 100.0
        total = home_points + away_points
        spread = home_points - away_points
        uncertainty = 9.0 + 0.08 * sqrt(max(total, 1.0))
        if ctx.injury_volatility:
            uncertainty *= 1.0 + ctx.injury_volatility
        return Projection(possessions, home_points, away_points, total, spread, uncertainty,
                          self._regime(ctx, possessions), ctx.data_quality)
