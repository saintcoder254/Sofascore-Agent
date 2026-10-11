from __future__ import annotations
import json
import sqlite3
import time
from typing import Any

class BasketballStore:
    """Auditable SQLite store for raw basketball observations and derived features."""
    def __init__(self, path: str = "basketball_titan.db"):
        self.path = path
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS raw_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                fixture_id TEXT NOT NULL,
                observed_at REAL NOT NULL,
                payload_hash TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(source, fixture_id, observed_at)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS feature_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id TEXT NOT NULL,
                snapshot_at REAL NOT NULL,
                features TEXT NOT NULL
            )""")
            db.commit()

    def put_raw(self, source: str, fixture_id: str, payload_hash: str, payload: Any):
        with self._connect() as db:
            db.execute(
                "INSERT INTO raw_observations(source,fixture_id,observed_at,payload_hash,payload) VALUES(?,?,?,?,?)",
                (source, fixture_id, time.time(), payload_hash, json.dumps(payload, sort_keys=True)),
            )
            db.commit()

    def put_features(self, fixture_id: str, features: dict):
        with self._connect() as db:
            db.execute(
                "INSERT INTO feature_snapshots(fixture_id,snapshot_at,features) VALUES(?,?,?)",
                (fixture_id, time.time(), json.dumps(features, sort_keys=True)),
            )
            db.commit()

    def counts(self) -> dict[str, int]:
        with self._connect() as db:
            raw = db.execute("SELECT COUNT(*) FROM raw_observations").fetchone()[0]
            features = db.execute("SELECT COUNT(*) FROM feature_snapshots").fetchone()[0]
        return {"raw_observations": raw, "feature_snapshots": features}
