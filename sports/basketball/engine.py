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
    league_average_rating: float = 114.0
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
    VERSION = "basketball-titan-1.1"

    @staticmethod
    def _blend(a: float, b: float, wa: float = 0.5) -> float:
        return wa * a + (1.0 - wa) * b

    @staticmethod
    def _matchup_offense(offense: float, opponent_defense: float, league_avg: float) -> float:
        # Ratings are points per 100 possessions. Defense is lower-is-better.
        # Anchor the matchup around the league mean rather than a hard-coded constant.
        opponent_delta = league_avg - opponent_defense
        return offense + 0.45 * opponent_delta

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
        home_eff = self._matchup_offense(ctx.home.offensive_rating, ctx.away.defensive_rating, ctx.league_average_rating)
        away_eff = self._matchup_offense(ctx.away.offensive_rating, ctx.home.defensive_rating, ctx.league_average_rating)
        home_eff += ctx.home_advantage + 0.25 * (ctx.rest_home - ctx.rest_away)
        away_eff += 0.25 * (ctx.rest_away - ctx.rest_home)
        home_points = possessions * home_eff / 100.0
        away_points = possessions * away_eff / 100.0
        total = home_points + away_points
        spread = home_points - away_points
        uncertainty = 9.0 + 0.08 * sqrt(max(total, 1.0))
        uncertainty *= 1.0 + max(0.0, ctx.injury_volatility)
        uncertainty *= 1.0 + max(0.0, 0.8 - ctx.data_quality) * 0.5
        return Projection(possessions, home_points, away_points, total, spread, uncertainty,
                          self._regime(ctx, possessions), ctx.data_quality)
