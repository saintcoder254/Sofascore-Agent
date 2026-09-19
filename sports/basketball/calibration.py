from __future__ import annotations
from dataclasses import dataclass
from math import log

@dataclass(frozen=True)
class CalibrationSummary:
    samples: int
    brier: float
    log_loss: float
    accuracy: float

def summarize(predictions: list[float], outcomes: list[float]) -> CalibrationSummary:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    n = len(predictions)
    if n == 0:
        return CalibrationSummary(0, 0.0, 0.0, 0.0)
    eps = 1e-12
    brier = sum((p-o)**2 for p,o in zip(predictions,outcomes))/n
    ll = -sum(o*log(max(eps,p)) + (1-o)*log(max(eps,1-p)) for p,o in zip(predictions,outcomes))/n
    accuracy = sum((p >= .5) == bool(o) for p,o in zip(predictions,outcomes))/n
    return CalibrationSummary(n,brier,ll,accuracy)
