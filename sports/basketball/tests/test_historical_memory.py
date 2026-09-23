import json
import tempfile
import unittest
from pathlib import Path

from sports.basketball.historical_memory import BasketballHistoricalMemory


class HistoricalMemoryTests(unittest.TestCase):
    def test_cutoff_prevents_future_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "memory.db"
            dataset = root / "pregame.jsonl"

            import sqlite3
            with sqlite3.connect(db) as con:
                con.execute("""CREATE TABLE raw_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    fixture_id TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    payload_hash TEXT NOT NULL,
                    payload TEXT NOT NULL)""")
                con.execute("""CREATE TABLE odds_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fixture_id TEXT NOT NULL,
                    market TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    odds REAL NOT NULL,
                    captured_at REAL NOT NULL,
                    source TEXT NOT NULL,
                    is_closing INTEGER NOT NULL DEFAULT 0)""")
                con.execute(
                    "INSERT INTO raw_observations(source,fixture_id,observed_at,payload_hash,payload) VALUES(?,?,?,?,?)",
                    ("sofascore","old",90,"h",json.dumps({"homeTeam":{"id":1,"name":"Alpha"}})),
                )
                con.execute(
                    "INSERT INTO raw_observations(source,fixture_id,observed_at,payload_hash,payload) VALUES(?,?,?,?,?)",
                    ("sofascore","future",110,"h2",json.dumps({"homeTeam":{"id":1,"name":"Alpha"}})),
                )
                con.execute(
                    "INSERT INTO odds_snapshots(fixture_id,market,selection,odds,captured_at,source,is_closing) VALUES(?,?,?,?,?,?,?)",
                    ("old","totals","over",1.9,95,"book",0),
                )
                con.execute(
                    "INSERT INTO odds_snapshots(fixture_id,market,selection,odds,captured_at,source,is_closing) VALUES(?,?,?,?,?,?,?)",
                    ("old","totals","over",1.7,110,"book",1),
                )

            memory = BasketballHistoricalMemory(str(db), str(dataset))
            context = memory.build_context(
                cutoff_timestamp=100,
                fixture_id="old",
                home_team_id="1",
            )

            self.assertEqual(len(context.raw_observations), 1)
            self.assertEqual(len(context.market_snapshots), 1)
            self.assertEqual(context.raw_observations[0]["fixture_id"], "old")


if __name__ == "__main__":
    unittest.main()
