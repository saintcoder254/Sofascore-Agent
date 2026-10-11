from __future__ import annotations
from dataclasses import asdict
import time
from .dataset import HistoricalDataset, PregameRow
from .matching import match_fixture

class BasketballDatasetBuilder:
    """Materializes leakage-safe pregame rows from verified results + market snapshots."""

    def __init__(self, dataset: HistoricalDataset):
        self.dataset = dataset

    def build_row(self, fixture: dict, features: dict, market: dict,
                  verified_result: dict, snapshot_timestamp: float) -> PregameRow | None:
        tip = float(fixture["scheduled_tipoff"])
        if snapshot_timestamp >= tip:
            return None
        if not verified_result.get("completed"):
            return None
        if not match_fixture(
            fixture["home_team"], fixture["away_team"], tip,
            verified_result["home_team"], verified_result["away_team"], tip
        ):
            return None
        return PregameRow(
            fixture_id=str(fixture["fixture_id"]),
            competition=str(fixture.get("competition", "")),
            scheduled_tipoff=tip,
            snapshot_timestamp=float(snapshot_timestamp),
            home_team_id=str(fixture["home_team_id"]),
            away_team_id=str(fixture["away_team_id"]),
            features=features,
            market=market,
            target_home_win=int(verified_result["home_win"]),
            target_total=float(verified_result["total"]),
            verified=True,
        )

    def append_verified(self, fixture: dict, features: dict, market: dict,
                        verified_result: dict, snapshot_timestamp: float) -> bool:
        row = self.build_row(fixture, features, market, verified_result, snapshot_timestamp)
        if row is None:
            return False
        self.dataset.append(row)
        return True
