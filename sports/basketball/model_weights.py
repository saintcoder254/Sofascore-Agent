from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ModelPerformance:
    model: str
    brier: float
    log_loss: float
    samples: int
    calibration_gap: float

def weight_models(performance: list[ModelPerformance], min_samples: int = 250) -> dict[str, float]:
    eligible = [p for p in performance if p.samples >= min_samples]
    if not eligible:
        return {}
    raw = {}
    for p in eligible:
        # Lower error and lower calibration gap receive greater weight.
        raw[p.model] = 1.0 / max(1e-6, p.brier + p.log_loss + p.calibration_gap)
    total = sum(raw.values())
    return {model: value / total for model, value in raw.items()}
