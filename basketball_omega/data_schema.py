"""Point-in-time basketball data contracts.

This module intentionally has no imports from football/UMIOS modules.
All timestamps are UTC epoch seconds and all observations are immutable snapshots.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class TeamSnapshot:
    team_id: str
    name: str
    captured_at: float
    stats: Dict[str, float] = field(default_factory=dict)
    source: str = "unknown"
    source_timestamp: Optional[float] = None

@dataclass(frozen=True)
class PlayerSnapshot:
    player_id: str
    team_id: str
    captured_at: float
    stats: Dict[str, float] = field(default_factory=dict)
    status: str = "available"
    expected_minutes: Optional[float] = None
    minutes_low: Optional[float] = None
    minutes_high: Optional[float] = None
    source: str = "unknown"
    source_timestamp: Optional[float] = None

@dataclass(frozen=True)
class LineupSnapshot:
    team_id: str
    player_ids: tuple[str, ...]
    captured_at: float
    expected_minutes: float
    net_rating: Optional[float] = None
    possessions: Optional[float] = None
    source: str = "unknown"

@dataclass(frozen=True)
class MarketSnapshot:
    fixture_id: str
    captured_at: float
    market: str
    line: Optional[float]
    price: Optional[float]
    side: Optional[str]
    source: str
    is_opening: bool = False
    is_closing: bool = False

@dataclass(frozen=True)
class BasketballSnapshot:
    fixture_id: str
    captured_at: float
    home_team_id: str
    away_team_id: str
    teams: Dict[str, TeamSnapshot] = field(default_factory=dict)
    players: Dict[str, PlayerSnapshot] = field(default_factory=dict)
    lineups: List[LineupSnapshot] = field(default_factory=list)
    markets: List[MarketSnapshot] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "BASKETBALL-PIT-v1"

    def point_in_time(self, at: float) -> "BasketballSnapshot":
        if at >= self.captured_at:
            return self
        players = {k:v for k,v in self.players.items() if v.captured_at <= at}
        teams = {k:v for k,v in self.teams.items() if v.captured_at <= at}
        lineups = [x for x in self.lineups if x.captured_at <= at]
        markets = [x for x in self.markets if x.captured_at <= at]
        return BasketballSnapshot(self.fixture_id, at, self.home_team_id, self.away_team_id,
                                  teams, players, lineups, markets, dict(self.context), self.schema_version)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.fixture_id: errors.append("fixture_id_missing")
        if not self.home_team_id or not self.away_team_id: errors.append("team_ids_missing")
        if self.home_team_id == self.away_team_id: errors.append("home_away_same_team")
        if self.captured_at <= 0: errors.append("invalid_captured_at")
        for p in self.players.values():
            if p.captured_at > self.captured_at: errors.append(f"future_player_snapshot:{p.player_id}")
            if p.minutes_low is not None and p.minutes_high is not None and p.minutes_low > p.minutes_high:
                errors.append(f"invalid_minutes_interval:{p.player_id}")
        return errors
