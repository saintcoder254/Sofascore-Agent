from __future__ import annotations
import json
import sqlite3
from .market_data import OddsSnapshot

class BasketballMarketStore:
    def __init__(self, path: str = "basketball_titan.db"):
        self.path = path
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS odds_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id TEXT NOT NULL,
                market TEXT NOT NULL,
                selection TEXT NOT NULL,
                odds REAL NOT NULL,
                captured_at REAL NOT NULL,
                source TEXT NOT NULL,
                is_closing INTEGER NOT NULL DEFAULT 0
            )""")
            db.commit()

    def put(self, snapshot: OddsSnapshot):
        with self._connect() as db:
            db.execute(
                "INSERT INTO odds_snapshots(fixture_id,market,selection,odds,captured_at,source,is_closing) VALUES(?,?,?,?,?,?,?)",
                (snapshot.fixture_id, snapshot.market, snapshot.selection, snapshot.odds,
                 snapshot.captured_at, snapshot.source, int(snapshot.is_closing)),
            )
            db.commit()

    def latest(self, fixture_id: str, market: str, selection: str):
        with self._connect() as db:
            return db.execute(
                """SELECT odds,captured_at,source,is_closing FROM odds_snapshots
                   WHERE fixture_id=? AND market=? AND selection=?
                   ORDER BY captured_at DESC LIMIT 1""",
                (fixture_id, market, selection),
            ).fetchone()
