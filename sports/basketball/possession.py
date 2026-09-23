from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import random

@dataclass(frozen=True)
class PossessionProfile:
    possessions: float
    points_per_possession: float
    turnover_rate: float = 0.13
    offensive_rebound_rate: float = 0.25
    three_rate: float = 0.38
    free_throw_rate: float = 0.18

@dataclass(frozen=True)
class PossessionPath:
    home_points: int
    away_points: int
    possessions: int
    lead_at_half: int

class PossessionSimulator:
    """State-oriented approximation; designed so a future play-by-play model can replace it."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def _possession_points(self, ppp: float, profile: PossessionProfile, trailing: bool) -> int:
        u = self.rng.random()
        # Explicit outcome mixture prevents treating scoring as a simple normal variable.
        three = u < profile.three_rate
        if three:
            made = self.rng.random() < max(0.0, min(1.0, ppp / 3.0))
            return 3 if made else 0
        ft = self.rng.random() < profile.free_throw_rate
        if ft:
            return 1 if self.rng.random() < 0.76 else 2
        return 2 if self.rng.random() < max(0.0, min(1.0, ppp / 2.0)) else 0

    def run(self, home: PossessionProfile, away: PossessionProfile,
            possessions: Optional[int] = None) -> PossessionPath:
        n = possessions or max(70, int(round((home.possessions + away.possessions) / 2)))
        hp = ap = 0
        half = max(1, n // 2)
        for i in range(n):
            if i % 2 == 0:
                hp += self._possession_points(home.points_per_possession, home, hp < ap)
            else:
                ap += self._possession_points(away.points_per_possession, away, ap < hp)
        return PossessionPath(hp, ap, n, hp if hp > ap else -ap if ap > hp else 0)
