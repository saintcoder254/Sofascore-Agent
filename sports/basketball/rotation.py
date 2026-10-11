from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class RotationPlayer:
    player_id: str
    expected_minutes: float
    minute_sd: float = 2.5
    availability: float = 1.0
    impact_per_100: float = 0.0
    usage: float = 0.0

@dataclass(frozen=True)
class RotationSummary:
    expected_impact: float
    minutes_uncertainty: float
    availability: float
    continuity: float

def summarize_rotation(players: list[RotationPlayer]) -> RotationSummary:
    if not players:
        return RotationSummary(0.0, 0.0, 0.0, 0.0)
    weighted = sum(max(0.0, p.expected_minutes) * p.availability * p.impact_per_100 for p in players)
    minutes = sum(max(0.0, p.expected_minutes) for p in players)
    uncertainty = sqrt(sum((max(0.0, p.minute_sd) * max(0.0, p.usage)) ** 2 for p in players))
    availability = sum(p.availability for p in players) / len(players)
    continuity = min(1.0, minutes / 240.0) * availability
    return RotationSummary(weighted / max(minutes, 1.0), uncertainty, availability, continuity)
