"""Independent SQLite point-in-time ledger for basketball.

No football store, UMIOS probability engine, or football market model is imported.
"""
import json
import sqlite3
from dataclasses import asdict
from typing import Optional
from basketball_omega.data_schema import BasketballSnapshot

class BasketballSnapshotStore:
    def __init__(self, path: str = "basketball_omega.db"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS basketball_snapshots (
                fixture_id TEXT NOT NULL,
                captured_at REAL NOT NULL,
                schema_version TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (fixture_id, captured_at)
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_basketball_snapshots_fixture_time
            ON basketball_snapshots(fixture_id, captured_at)
        """)
        self.db.commit()

    def put(self, snapshot: BasketballSnapshot) -> None:
        errors = snapshot.validate()
        if errors:
            raise ValueError("invalid basketball snapshot: " + ",".join(errors))
        self.db.execute(
            "INSERT OR REPLACE INTO basketball_snapshots VALUES (?,?,?,?)",
            (snapshot.fixture_id, snapshot.captured_at, snapshot.schema_version,
             json.dumps(asdict(snapshot), sort_keys=True, separators=(",", ":"))),
        )
        self.db.commit()

    def latest_before(self, fixture_id: str, at: float) -> Optional[dict]:
        row = self.db.execute(
            """SELECT payload_json FROM basketball_snapshots
               WHERE fixture_id=? AND captured_at<=?
               ORDER BY captured_at DESC LIMIT 1""",
            (fixture_id, at),
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def close(self) -> None:
        self.db.close()
