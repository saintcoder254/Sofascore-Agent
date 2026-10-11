from __future__ import annotations
from dataclasses import dataclass
from math import log, exp

@dataclass(frozen=True)
class TrainingRow:
    """One historical pregame observation. No post-tip information is permitted."""
    home_points: float
    away_points: float
    predicted_home_win: float
    predicted_total: float
    actual_total: float
    market_total: float | None = None
    closing_total: float | None = None

@dataclass(frozen=True)
class TrainingMetrics:
    rows: int
    brier_moneyline: float
    mae_total: float
    closing_total_mae: float
    mean_total_edge: float

def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    if not predictions:
        return 0.0
    return sum((p - y) ** 2 for p, y in zip(predictions, outcomes)) / len(predictions)

def evaluate(rows: list[TrainingRow]) -> TrainingMetrics:
    if not rows:
        return TrainingMetrics(0, 0.0, 0.0, 0.0, 0.0)
    win_preds = [r.predicted_home_win for r in rows]
    wins = [int(r.home_points > r.away_points) for r in rows]
    total_errors = [abs(r.predicted_total - r.actual_total) for r in rows]
    closing_errors = [abs(r.predicted_total - r.closing_total) for r in rows if r.closing_total is not None]
    edges = [r.predicted_total - r.market_total for r in rows if r.market_total is not None]
    return TrainingMetrics(
        len(rows),
        brier_score(win_preds, wins),
        sum(total_errors) / len(total_errors),
        sum(closing_errors) / len(closing_errors) if closing_errors else 0.0,
        sum(edges) / len(edges) if edges else 0.0,
    )

def chronological_split(rows: list[TrainingRow], train_fraction: float = 0.70):
    """Time-ordered split; prevents future leakage into training."""
    ordered = list(rows)
    cut = int(len(ordered) * train_fraction)
    return ordered[:cut], ordered[cut:]
