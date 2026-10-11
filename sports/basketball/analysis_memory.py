from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .historical_memory import BasketballHistoricalMemory, HistoricalContext


@dataclass(frozen=True)
class AnalysisMemoryBundle:
    """The historical-memory package an analysis must consume before modeling."""

    context: HistoricalContext
    queried: bool = True
    leakage_guard: bool = True

    def as_dict(self) -> dict[str, Any]:
        payload = self.context.as_dict()
        payload["memory_query"] = {
            "queried": self.queried,
            "leakage_guard": self.leakage_guard,
            "required_before_modeling": True,
        }
        return payload


class BasketballAnalysisMemoryGate:
    """Mandatory, cutoff-aware memory retrieval boundary for analysis requests.

    The gate does not alter model probabilities itself. It guarantees that an
    analysis has a historical context object available before downstream
    feature engineering, simulation, calibration, and decision layers run.
    """

    def __init__(self, memory: BasketballHistoricalMemory):
        self.memory = memory

    def query(
        self,
        *,
        cutoff_timestamp: float,
        fixture_id: Optional[str] = None,
        home_team_id: Optional[str] = None,
        away_team_id: Optional[str] = None,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
        raw_limit: int = 250,
        market_limit: int = 500,
        verified_limit: int = 250,
    ) -> AnalysisMemoryBundle:
        if cutoff_timestamp <= 0:
            raise ValueError("cutoff_timestamp must be a positive epoch timestamp")

        context = self.memory.build_context(
            cutoff_timestamp=cutoff_timestamp,
            fixture_id=fixture_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_team=home_team,
            away_team=away_team,
            raw_limit=raw_limit,
            market_limit=market_limit,
            verified_limit=verified_limit,
        )
        return AnalysisMemoryBundle(context=context)
