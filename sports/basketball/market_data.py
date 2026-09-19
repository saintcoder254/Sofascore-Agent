from __future__ import annotations
from dataclasses import dataclass
import time
from typing import Iterable

@dataclass(frozen=True)
class OddsSnapshot:
    fixture_id: str
    market: str
    selection: str
    odds: float
    captured_at: float
    source: str
    is_closing: bool = False

def decimal_to_implied(odds: float) -> float:
    if odds <= 1:
        raise ValueError("decimal odds must be > 1")
    return 1.0 / odds

def remove_vig(odds_by_selection: dict[str, float]) -> dict[str, float]:
    implied = {k: decimal_to_implied(v) for k, v in odds_by_selection.items()}
    total = sum(implied.values())
    if total <= 0:
        return {k: 0.0 for k in implied}
    return {k: v / total for k, v in implied.items()}

def line_movement(opening: float, current: float) -> float:
    return current - opening
