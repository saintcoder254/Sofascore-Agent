from __future__ import annotations
from dataclasses import dataclass
from statistics import mean, pstdev
from .training import TrainingMetrics

@dataclass(frozen=True)
class ModelSignal:
    model: str
    probability: float
    confidence: float
    data_quality: float

@dataclass(frozen=True)
class ArbiterResult:
    probability: float
    dispersion: float
    confidence: float
    decision: str

class BasketballArbiter:
    """Combines independent model signals and abstains when disagreement is material."""
    def combine(self, signals: list[ModelSignal], min_confidence: float = 0.60,
                max_dispersion: float = 0.12) -> ArbiterResult:
        valid = [s for s in signals if 0 <= s.probability <= 1 and s.data_quality > 0]
        if not valid:
            return ArbiterResult(0.5, 1.0, 0.0, "NO_BET")
        weights = [max(0.01, s.confidence * s.data_quality) for s in valid]
        probability = sum(s.probability * w for s, w in zip(valid, weights)) / sum(weights)
        dispersion = pstdev([s.probability for s in valid]) if len(valid) > 1 else 0.0
        confidence = min(1.0, mean(weights) * (1.0 - min(1.0, dispersion * 3)))
        decision = "BET" if confidence >= min_confidence and dispersion <= max_dispersion else "NO_BET"
        return ArbiterResult(probability, dispersion, confidence, decision)
