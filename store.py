import sqlite3, json

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
