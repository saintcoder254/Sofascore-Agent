from __future__ import annotations
from dataclasses import dataclass
from math import exp
from random import Random

@dataclass(frozen=True)
class ShotProfile:
    three_rate: float = 0.38
    two_pct: float = 0.53
    three_pct: float = 0.36
    ft_rate: float = 0.18
    ft_pct: float = 0.76
    turnover_rate: float = 0.13
    offensive_rebound_rate: float = 0.25

@dataclass(frozen=True)
class PossessionOutcome:
    points: int
    turnover: bool
    offensive_rebound: bool
    shot_type: str

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

class ShotOutcomeModel:
    """Explicit possession outcome model; efficiencies are probabilities, not PPP proxies."""
    def __init__(self, seed: int | None = None):
        self.rng = Random(seed)

    def sample(self, profile: ShotProfile) -> PossessionOutcome:
        if self.rng.random() < clamp(profile.turnover_rate, 0.01, 0.35):
            return PossessionOutcome(0, True, False, "turnover")

        # Foul/free-throw possessions are modeled separately from field-goal attempts.
        if self.rng.random() < clamp(profile.ft_rate, 0.02, 0.45):
            makes = 0
            rolls = 2 if self.rng.random() < 0.82 else 1
            for _ in range(rolls):
                makes += int(self.rng.random() < clamp(profile.ft_pct, 0.45, 0.95))
            return PossessionOutcome(makes, False, False, "free_throw")

        if self.rng.random() < clamp(profile.three_rate, 0.05, 0.65):
            made = self.rng.random() < clamp(profile.three_pct, 0.20, 0.50)
            if made:
                return PossessionOutcome(3, False, False, "three")
            orb = self.rng.random() < clamp(profile.offensive_rebound_rate, 0.05, 0.45)
            return PossessionOutcome(0, False, orb, "three_miss")

        made = self.rng.random() < clamp(profile.two_pct, 0.35, 0.70)
        if made:
            return PossessionOutcome(2, False, False, "two")
        orb = self.rng.random() < clamp(profile.offensive_rebound_rate, 0.05, 0.45)
        return PossessionOutcome(0, False, orb, "two_miss")
