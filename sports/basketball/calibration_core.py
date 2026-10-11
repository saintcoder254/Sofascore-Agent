from __future__ import annotations
from dataclasses import dataclass
from math import log

@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    predicted_mean: float
    observed_rate: float
    gap: float

@dataclass(frozen=True)
class CalibrationReport:
    bins: tuple[CalibrationBin, ...]
    mean_absolute_gap: float
    sample_count: int

def calibration_report(predictions: list[float], outcomes: list[int], bins: int = 10) -> CalibrationReport:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        return CalibrationReport((), 0.0, 0)
    result = []
    width = 1.0 / bins
    for i in range(bins):
        lo, hi = i * width, (i + 1) * width
        selected = [(p, y) for p, y in zip(predictions, outcomes)
                    if (lo <= p < hi) or (i == bins - 1 and p == hi)]
        if not selected:
            continue
        pmean = sum(p for p, _ in selected) / len(selected)
        observed = sum(y for _, y in selected) / len(selected)
        result.append(CalibrationBin(lo, hi, len(selected), pmean, observed, abs(pmean - observed)))
    gap = sum(x.gap for x in result) / len(result) if result else 0.0
    return CalibrationReport(tuple(result), gap, len(predictions))
