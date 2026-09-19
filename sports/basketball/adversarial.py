from __future__ import annotations
from dataclasses import dataclass, replace
from .engine import BasketballEngine, GameContext, Projection

@dataclass(frozen=True)
class StressCase:
    name: str
    pace_multiplier: float = 1.0
    shooting_multiplier: float = 1.0
    injury_volatility: float | None = None

@dataclass(frozen=True)
class StressResult:
    name: str
    total_points: float
    spread_home: float
    delta_total: float
    delta_spread: float

def stress_test(ctx: GameContext, cases: list[StressCase]) -> list[StressResult]:
    base = BasketballEngine().project(ctx)
    results = []
    for case in cases:
        h = replace(ctx.home, pace=ctx.home.pace * case.pace_multiplier,
                    offensive_rating=ctx.home.offensive_rating * case.shooting_multiplier)
        a = replace(ctx.away, pace=ctx.away.pace * case.pace_multiplier,
                    offensive_rating=ctx.away.offensive_rating * case.shooting_multiplier)
        stressed = BasketballEngine().project(replace(
            ctx, home=h, away=a,
            injury_volatility=ctx.injury_volatility if case.injury_volatility is None else case.injury_volatility
        ))
        results.append(StressResult(case.name, stressed.total_points, stressed.spread_home,
                                    stressed.total_points - base.total_points,
                                    stressed.spread_home - base.spread_home))
    return results
