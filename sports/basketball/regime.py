from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RegimeSignal:
    name: str
    volatility_multiplier: float
    confidence: float
    reasons: tuple[str, ...]

def classify_regime(estimated_possessions: float, injury_volatility: float = 0.0,
                    data_quality: float = 1.0) -> RegimeSignal:
    reasons = []
    multiplier = 1.0
    if estimated_possessions >= 103:
        name = "fast_pace"; reasons.append("estimated possessions above fast-pace threshold")
    elif estimated_possessions <= 94:
        name = "slow_pace"; reasons.append("estimated possessions below slow-pace threshold")
    else:
        name = "neutral"
    if injury_volatility >= .25:
        name = "injury_high_variance"; multiplier *= 1.25
        reasons.append("meaningful lineup/injury uncertainty")
    confidence = max(0.0, min(1.0, data_quality * (1.0 - min(.5, injury_volatility))))
    return RegimeSignal(name, multiplier, confidence, tuple(reasons))
