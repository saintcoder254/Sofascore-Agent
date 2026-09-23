from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean

from .analysis_memory import BasketballAnalysisMemoryGate
from .engine import BasketballEngine, GameContext, TeamProfile
from .simulation import SimulationResult, simulate


@dataclass(frozen=True)
class AnalysisResult:
    memory: dict
    projection: dict
    simulation: dict


def _events_from_context(context: dict) -> list[dict]:
    events: list[dict] = []
    for row in context.get("raw_observations", []):
        payload = row.get("payload")
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _team_stats(events: list[dict], team_id: str | None) -> tuple[int, float, float, float, float, float]:
    rows = []
    for event in events:
        home = event.get("homeScore") or {}
        away = event.get("awayScore") or {}
        if event.get("status", {}).get("type") != "finished":
            continue
        if "current" not in home or "current" not in away:
            continue
        if str(event.get("homeTeam", {}).get("id")) == str(team_id):
            rows.append((float(home["current"]), float(away["current"])))
        elif str(event.get("awayTeam", {}).get("id")) == str(team_id):
            rows.append((float(away["current"]), float(home["current"])))
    if not rows:
        return 0, 0.0, 0.0, 0.0, 0.0, 0.0
    pf = mean(x[0] for x in rows)
    pa = mean(x[1] for x in rows)
    totals = [x[0] + x[1] for x in rows]
    variance = mean((x - mean(totals)) ** 2 for x in totals) if len(totals) > 1 else 0.0
    return len(rows), pf, pa, mean(totals) / 2.25, mean(totals), variance ** 0.5


def _profile(events: list[dict], team_id: str | None) -> TeamProfile:
    games, pf, pa, pace, _, _ = _team_stats(events, team_id)
    if games == 0:
        return TeamProfile(114.0, 114.0, 100.0)
    return TeamProfile(
        offensive_rating=pf / max(pace, 1.0) * 100.0,
        defensive_rating=pa / max(pace, 1.0) * 100.0,
        pace=pace,
    )


class BasketballAnalysisService:
    """End-to-end pregame path: memory -> features -> projection -> simulation."""

    def __init__(self, memory_gate: BasketballAnalysisMemoryGate):
        self.memory_gate = memory_gate
        self.engine = BasketballEngine()

    def analyze(
        self,
        *,
        cutoff_timestamp: float,
        fixture_id: str | None = None,
        home_team_id: str | None = None,
        away_team_id: str | None = None,
        home_team: str | None = None,
        away_team: str | None = None,
        market_total: float | None = None,
        market_spread_home: float | None = None,
        simulations: int = 10_000,
    ) -> AnalysisResult:
        memory = self.memory_gate.query(
            cutoff_timestamp=cutoff_timestamp,
            fixture_id=fixture_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_team=home_team,
            away_team=away_team,
        )
        memory_dict = memory.as_dict()
        events = _events_from_context(memory_dict)
        home = _profile(events, home_team_id)
        away = _profile(events, away_team_id)

        quality = min(1.0, max(0.0, len(events) / 20.0))
        context = GameContext(
            home=home,
            away=away,
            market_total=market_total,
            market_spread_home=market_spread_home,
            data_quality=quality,
            metadata={"historical_memory_rows": len(events)},
        )
        projection = self.engine.project(context)
        sim = simulate(
            projection,
            simulations=max(1, min(simulations, 10_000)),
            total_line=market_total,
            home_spread_line=market_spread_home,
        )

        return AnalysisResult(
            memory=memory_dict,
            projection=asdict(projection),
            simulation=asdict(sim),
        )
