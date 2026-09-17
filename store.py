import sqlite3, json, time


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('''CREATE TABLE IF NOT EXISTS snapshots(
            fixture_id TEXT NOT NULL,
            retrieved_at REAL NOT NULL,
            payload_hash TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY(fixture_id, retrieved_at)
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS current(
            fixture_id TEXT PRIMARY KEY,
            retrieved_at REAL NOT NULL,
            payload_hash TEXT NOT NULL,
            payload TEXT NOT NULL
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS predictions(
            prediction_id TEXT PRIMARY KEY,
            fixture_id TEXT NOT NULL,
            market TEXT NOT NULL,
            predicted_probability REAL NOT NULL,
            selection TEXT,
            odds REAL,
            predicted_at REAL NOT NULL,
            outcome REAL,
            outcome_at REAL,
            model_version TEXT NOT NULL,
            features_json TEXT NOT NULL
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS evolution_runs(
            run_id TEXT PRIMARY KEY,
            created_at REAL NOT NULL,
            result_json TEXT NOT NULL
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS evolution_candidates(
            candidate_id TEXT PRIMARY KEY,
            created_at REAL NOT NULL,
            candidate_json TEXT NOT NULL
        )''')
        self.db.commit()

    def get_current(self, fixture_id):
        row = self.db.execute(
            "SELECT retrieved_at,payload_hash,payload FROM current WHERE fixture_id=?",
            (fixture_id,)).fetchone()
        if not row:
            return None
        return {"retrieved_at": row[0], "payload_hash": row[1], "payload": json.loads(row[2])}

    def put(self, fixture_id, retrieved_at, payload_hash, payload):
        raw = json.dumps(payload, separators=(",", ":"))
        self.db.execute("INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?)",
                        (fixture_id, retrieved_at, payload_hash, raw))
        self.db.execute("INSERT OR REPLACE INTO current VALUES(?,?,?,?)",
                        (fixture_id, retrieved_at, payload_hash, raw))
        self.db.commit()

    def current(self):
        rows = self.db.execute(
            "SELECT fixture_id,retrieved_at,payload_hash,payload FROM current").fetchall()
        return [{"fixture_id": r[0], "retrieved_at": r[1],
                 "payload_hash": r[2], "payload": json.loads(r[3])} for r in rows]

    def add_prediction(self, prediction_id, fixture_id, market, predicted_probability,
                       selection=None, odds=None, predicted_at=None, model_version="unknown",
                       features=None):
        self.db.execute(
            """INSERT OR REPLACE INTO predictions
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (prediction_id, str(fixture_id), market, float(predicted_probability), selection,
             None if odds is None else float(odds), predicted_at or time.time(), None, None,
             model_version, json.dumps(features or {}, separators=(",", ":"))))
        self.db.commit()

    def record_outcome(self, prediction_id, outcome, outcome_at=None):
        self.db.execute(
            "UPDATE predictions SET outcome=?, outcome_at=? WHERE prediction_id=?",
            (float(outcome), outcome_at or time.time(), prediction_id))
        self.db.commit()

    def predictions_with_outcomes(self):
        rows = self.db.execute(
            """SELECT prediction_id,fixture_id,market,predicted_probability,selection,odds,
            predicted_at,outcome,outcome_at,model_version,features_json
            FROM predictions WHERE outcome IS NOT NULL"""
        ).fetchall()
        return [
            {
                "prediction_id": r[0], "fixture_id": r[1], "market": r[2],
                "predicted_probability": r[3], "selection": r[4], "odds": r[5],
                "predicted_at": r[6], "outcome": r[7], "outcome_at": r[8],
                "model_version": r[9], "features": json.loads(r[10] or "{}")
            }
            for r in rows
        ]

    def prediction_count(self):
        return self.db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]

    def resolved_prediction_count(self):
        return self.db.execute("SELECT COUNT(*) FROM predictions WHERE outcome IS NOT NULL").fetchone()[0]

    def add_evolution_run(self, run_id, result):
        self.db.execute(
            "INSERT OR REPLACE INTO evolution_runs VALUES(?,?,?)",
            (run_id, time.time(), json.dumps(result, separators=(",", ":"))))
        self.db.commit()

    def latest_evolution_run(self):
        row = self.db.execute(
            "SELECT result_json FROM evolution_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return json.loads(row[0]) if row else None

    def add_candidate(self, candidate):
        self.db.execute(
            "INSERT OR REPLACE INTO evolution_candidates VALUES(?,?,?)",
            (candidate["candidate_id"], candidate.get("created_at", time.time()),
             json.dumps(candidate, separators=(",", ":"))))
        self.db.commit()

    def latest_candidates(self, limit=20):
        rows = self.db.execute(
            "SELECT candidate_json FROM evolution_candidates ORDER BY created_at DESC LIMIT ?",
            (int(limit),)).fetchall()
        return [json.loads(r[0]) for r in rows]
