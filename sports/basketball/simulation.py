from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List, Optional
from .engine import Projection

@dataclass
class SimulationResult:
    simulations: int
    home_win_probability: float
    over_probability: Optional[float]
    under_probability: Optional[float]
    spread_cover_probability: Optional[float]
    mean_total: float
    p10_total: float
    p50_total: float
    p90_total: float
    mean_margin: float

def _percentile(values: List[float], q: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)

def simulate(projection: Projection, simulations: int = 10_000,
             total_line: Optional[float] = None,
             home_spread_line: Optional[float] = None,
             seed: Optional[int] = None) -> SimulationResult:
    rng = random.Random(seed)
    totals, margins = [], []
    home_wins = overs = covers = 0
    sd_team = projection.uncertainty / 1.41421356237
    for _ in range(max(1, simulations)):
        shared = rng.gauss(0.0, sd_team * 0.35)
        hp = rng.gauss(projection.home_points, sd_team) + shared
        ap = rng.gauss(projection.away_points, sd_team) + shared
        margin, total = hp - ap, hp + ap
        margins.append(margin); totals.append(total)
        home_wins += int(margin > 0)
        if total_line is not None:
            overs += int(total > total_line)
        if home_spread_line is not None:
            covers += int(margin + home_spread_line > 0)
    n = len(totals)
    return SimulationResult(
        n, home_wins / n,
        None if total_line is None else overs / n,
        None if total_line is None else 1.0 - overs / n,
        None if home_spread_line is None else covers / n,
        sum(totals) / n,
        _percentile(totals, .10), _percentile(totals, .50), _percentile(totals, .90),
        sum(margins) / n
    )
