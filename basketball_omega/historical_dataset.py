"""Leakage-resistant historical example builder for Basketball OMEGA.

The builder separates prediction-time features from post-cutoff outcomes and
market states. It does not fetch external data; adapters can feed validated
BasketballSnapshot objects from any provider.
"""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List
from basketball_omega.data_schema import BasketballSnapshot


@dataclass(frozen=True)
class BasketballTrainingExample:
    fixture_id: str
    cutoff_at: float
    home_team_id: str
    away_team_id: str
    features: Dict[str, Any]
    target_home_win: int
    target_margin: float
    target_total: float
    outcome_at: float


class BasketballPITDatasetBuilder:
    """Build chronological examples without exposing future observations."""

    def build_example(
        self,
        snapshot: BasketballSnapshot,
        cutoff_at: float,
        target_home_win: int,
        target_margin: float,
        target_total: float,
        outcome_at: float,
    ) -> BasketballTrainingExample:
        if outcome_at <= cutoff_at:
            raise ValueError("outcome_must_follow_prediction_cutoff")
        if snapshot.captured_at < cutoff_at:
            # A snapshot may be an earlier acquisition; that is fine only if
            # all of its observations are also no later than the cutoff.
            snap = snapshot.point_in_time(cutoff_at)
        else:
            snap = snapshot.point_in_time(cutoff_at)

        errors = snap.validate()
        if errors:
            raise ValueError("invalid_snapshot:" + ",".join(errors))

        teams = {
            team_id: dict(team.stats)
            for team_id, team in snap.teams.items()
        }
        players = {
            pid: {
                "team_id": p.team_id,
                "stats": dict(p.stats),
                "status": p.status,
                "expected_minutes": p.expected_minutes,
                "minutes_low": p.minutes_low,
                "minutes_high": p.minutes_high,
            }
            for pid, p in snap.players.items()
        }
        lineups = [
            {
                "team_id": x.team_id,
                "player_ids": list(x.player_ids),
                "expected_minutes": x.expected_minutes,
                "net_rating": x.net_rating,
                "possessions": x.possessions,
            }
            for x in snap.lineups
        ]
        markets = [
            {
                "market": x.market,
                "line": x.line,
                "price": x.price,
                "side": x.side,
                "source": x.source,
                "is_opening": x.is_opening,
                "is_closing": x.is_closing,
            }
            for x in snap.markets
        ]

        features = {
            "teams": teams,
            "players": players,
            "lineups": lineups,
            "markets": markets,
            "context": dict(snap.context),
        }
        return BasketballTrainingExample(
            fixture_id=snap.fixture_id,
            cutoff_at=cutoff_at,
            home_team_id=snap.home_team_id,
            away_team_id=snap.away_team_id,
            features=features,
            target_home_win=int(target_home_win),
            target_margin=float(target_margin),
            target_total=float(target_total),
            outcome_at=float(outcome_at),
        )

    def chronological(
        self, examples: Iterable[BasketballTrainingExample]
    ) -> List[BasketballTrainingExample]:
        rows = sorted(examples, key=lambda x: (x.cutoff_at, x.fixture_id))
        for i, row in enumerate(rows):
            if row.outcome_at <= row.cutoff_at:
                raise ValueError(f"invalid_temporal_order:{row.fixture_id}")
            if i and row.cutoff_at < rows[i - 1].cutoff_at:
                raise ValueError("dataset_not_chronological")
        return rows
