from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .matching import normalize_team_name


@dataclass(frozen=True)
class HistoricalContext:
    fixture_id: Optional[str]
    cutoff_timestamp: float
    home_team_id: Optional[str]
    away_team_id: Optional[str]
    raw_observations: tuple[dict[str, Any], ...]
    market_snapshots: tuple[dict[str, Any], ...]
    verified_rows: tuple[dict[str, Any], ...]
    team_history: tuple[dict[str, Any], ...]
    source_counts: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "cutoff_timestamp": self.cutoff_timestamp,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "raw_observations": list(self.raw_observations),
            "market_snapshots": list(self.market_snapshots),
            "verified_rows": list(self.verified_rows),
            "team_history": list(self.team_history),
            "source_counts": dict(self.source_counts),
            "leakage_guard": "Only observations captured at or before cutoff_timestamp are returned.",
        }


class BasketballHistoricalMemory:
    """Persistent, time-aware retrieval layer for every basketball analysis.

    It reads the same SQLite stores used by acquisition, market collection, and
    verified pregame datasets. Retrieval is cutoff-aware so post-tip information
    cannot leak into a pregame analysis.
    """

    def __init__(
        self,
        db_path: str = "basketball_titan.db",
        dataset_path: str = "data/basketball/pregame.jsonl",
    ):
        self.db_path = db_path
        self.dataset_path = Path(dataset_path)

    def _connect(self):
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _team_ids_from_payload(payload: Any) -> set[str]:
        ids: set[str] = set()
        if not isinstance(payload, dict):
            return ids

        def walk(value: Any):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"id", "teamId", "homeTeamId", "awayTeamId"}:
                        if isinstance(item, (int, str)) and str(item).strip():
                            ids.add(str(item))
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)
        return ids

    @staticmethod
    def _team_names_from_payload(payload: Any) -> set[str]:
        names: set[str] = set()
        if not isinstance(payload, dict):
            return names

        def walk(value: Any):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"homeTeam", "awayTeam", "team"} and isinstance(item, dict):
                        name = item.get("name")
                        if name:
                            names.add(normalize_team_name(str(name)))
                    elif key in {"home_team", "away_team"} and isinstance(item, str):
                        names.add(normalize_team_name(item))
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)
        return names

    def _raw_history(
        self,
        cutoff_timestamp: float,
        team_ids: set[str],
        team_names: set[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        try:
            with self._connect() as db:
                rows = db.execute(
                    """SELECT source,fixture_id,observed_at,payload_hash,payload
                       FROM raw_observations
                       WHERE observed_at <= ?
                       ORDER BY observed_at DESC
                       LIMIT ?""",
                    (cutoff_timestamp, max(limit * 5, 500)),
                ).fetchall()
        except sqlite3.OperationalError:
            return []

        matched: list[dict[str, Any]] = []
        for source, fixture_id, observed_at, payload_hash, payload_text in rows:
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                continue
            ids = self._team_ids_from_payload(payload)
            names = self._team_names_from_payload(payload)
            if team_ids.intersection(ids) or team_names.intersection(names):
                matched.append({
                    "source": source,
                    "fixture_id": str(fixture_id),
                    "observed_at": float(observed_at),
                    "payload_hash": payload_hash,
                    "payload": payload,
                })
                if len(matched) >= limit:
                    break
        return matched

    def _market_history(
        self,
        cutoff_timestamp: float,
        fixture_id: Optional[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        if not fixture_id:
            return []
        try:
            with self._connect() as db:
                rows = db.execute(
                    """SELECT fixture_id,market,selection,odds,captured_at,source,is_closing
                       FROM odds_snapshots
                       WHERE fixture_id=? AND captured_at <= ?
                       ORDER BY captured_at DESC
                       LIMIT ?""",
                    (str(fixture_id), cutoff_timestamp, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            return []

        return [
            {
                "fixture_id": str(row[0]),
                "market": row[1],
                "selection": row[2],
                "odds": float(row[3]),
                "captured_at": float(row[4]),
                "source": row[5],
                "is_closing": bool(row[6]),
            }
            for row in rows
        ]

    def _verified_history(
        self,
        cutoff_timestamp: float,
        team_ids: set[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        if not self.dataset_path.exists():
            return []

        result: list[dict[str, Any]] = []
        try:
            lines = self.dataset_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []

        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not row.get("verified"):
                continue
            snapshot = float(row.get("snapshot_timestamp", 0))
            tip = float(row.get("scheduled_tipoff", 0))
            if snapshot > cutoff_timestamp or tip > cutoff_timestamp:
                continue
            ids = {str(row.get("home_team_id", "")), str(row.get("away_team_id", ""))}
            if team_ids and not team_ids.intersection(ids):
                continue
            result.append(row)
            if len(result) >= limit:
                break
        return result

    def build_context(
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
    ) -> HistoricalContext:
        team_ids = {
            str(x) for x in (home_team_id, away_team_id) if x is not None and str(x)
        }
        team_names = {
            normalize_team_name(x)
            for x in (home_team, away_team)
            if x
        }

        raw = self._raw_history(cutoff_timestamp, team_ids, team_names, raw_limit)
        market = self._market_history(cutoff_timestamp, fixture_id, market_limit)
        verified = self._verified_history(cutoff_timestamp, team_ids, verified_limit)

        source_counts: dict[str, int] = {}
        for row in raw:
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        if market:
            source_counts["odds_market"] = len(market)
        if verified:
            source_counts["verified_dataset"] = len(verified)

        team_history = [
            {
                "fixture_id": row["fixture_id"],
                "observed_at": row["observed_at"],
                "source": row["source"],
                "payload": row["payload"],
            }
            for row in raw
        ]

        return HistoricalContext(
            fixture_id=fixture_id,
            cutoff_timestamp=cutoff_timestamp,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            raw_observations=tuple(raw),
            market_snapshots=tuple(market),
            verified_rows=tuple(verified),
            team_history=tuple(team_history),
            source_counts=source_counts,
        )
