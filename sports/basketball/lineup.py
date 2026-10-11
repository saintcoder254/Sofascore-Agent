from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional

@dataclass(frozen=True)
class PlayerImpact:
    player_id: str
    net_rating: float
    usage: float = 0.0
    expected_minutes: float = 0.0
    availability: float = 1.0

def lineup_adjustment(players: Iterable[PlayerImpact], baseline_net: float = 0.0) -> float:
    """Minute-weighted lineup impact. Availability scales expected contribution."""
    players = list(players)
    minutes = sum(max(0.0, p.expected_minutes) for p in players)
    if minutes <= 0:
        return baseline_net
    weighted = sum(p.net_rating * max(0.0, p.expected_minutes) * max(0.0, min(1.0, p.availability))
                   for p in players) / minutes
    return baseline_net + weighted

def availability_quality(players: Iterable[PlayerImpact]) -> Optional[float]:
    players = list(players)
    if not players:
        return None
    minutes = sum(max(0.0, p.expected_minutes) for p in players)
    if minutes <= 0:
        return None
    return sum(max(0.0, p.expected_minutes) * max(0.0, min(1.0, p.availability))
               for p in players) / minutes
