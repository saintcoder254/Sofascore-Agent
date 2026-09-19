from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

@dataclass(frozen=True)
class TeamFeatures:
    offensive_rating: float
    defensive_rating: float
    pace: float
    shot: object
    rest_days: float = 1.0
    travel_km: float = 0.0
    rolling_games: int = 10

@dataclass(frozen=True)
class DataFreshness:
    as_of: datetime
    max_age_minutes: float
    source_count: int

    @property
    def score(self) -> float:
        age = max(0.0, (datetime.now(timezone.utc) - self.as_of).total_seconds() / 60.0)
        freshness = 1.0 if age <= self.max_age_minutes else max(0.0, 1.0 - (age - self.max_age_minutes) / 240.0)
        source_bonus = min(1.0, self.source_count / 3.0)
        return 0.7 * freshness + 0.3 * source_bonus

def normalize_rate(value: float, default: float = 0.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, value))
