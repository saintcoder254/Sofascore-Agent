"""OMEGA case-database mesh.

Every fixture/case receives an isolated SQLite database plus a central registry.
Evidence, model runs, predictions, arbiter decisions, failures, and integrity
events are retained per case and linked through a tamper-evident hash chain.
"""
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path


class CaseDatabase:
    VERSION = "OMEGA-CASE-DB-v1"

    def __init__(self, path, case_id):
        self.path = str(path)
        self.case_id = str(case_id)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._schema()

    def _schema(self):
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS case_meta(
                case_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                schema_version TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                stage TEXT NOT NULL,
                agent TEXT NOT NULL,
                source TEXT,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                parent_hash TEXT,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trust_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                state TEXT NOT NULL,
                envelope_hash TEXT,
                hard_blocks_json TEXT NOT NULL,
                envelope_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                model TEXT NOT NULL,
                market TEXT,
                simulations INTEGER,
                input_hash TEXT,
                output_hash TEXT NOT NULL,
                output_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS market_snapshots(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                market TEXT NOT NULL,
                selection TEXT,
                odds REAL,
                implied_probability REAL,
                source TEXT,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS predictions(
                prediction_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                market TEXT NOT NULL,
                selection TEXT,
                probability REAL,
                odds REAL,
                edge REAL,
                expected_value REAL,
                model TEXT NOT NULL,
                prediction_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS arbiter_decisions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                state TEXT NOT NULL,
                reason TEXT,
                blockers_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                decision_hash TEXT NOT NULL,
                decision_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS failures(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                failure_code TEXT NOT NULL,
                severity TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_chain(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                event_type TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                parent_hash TEXT,
                chain_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_obs_stage ON observations(stage);
            CREATE INDEX IF NOT EXISTS idx_obs_source ON observations(source);
            CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_chain(event_type);
            """
        )
        now = time.time()
        self.db.execute(
            "INSERT OR IGNORE INTO case_meta(case_id,created_at,updated_at,status,schema_version) VALUES(?,?,?,?,?)",
            (self.case_id, now, now, "OPEN", self.VERSION),
        )
        self.db.commit()

    @staticmethod
    def _canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def _hash(cls, value):
        return hashlib.sha256(cls._canonical(value).encode()).hexdigest()

    def _last_chain_hash(self):
        row = self.db.execute("SELECT chain_hash FROM audit_chain ORDER BY sequence DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def _append_chain(self, event_type, payload):
        raw = self._canonical(payload)
        payload_hash = hashlib.sha256(raw.encode()).hexdigest()
        parent = self._last_chain_hash()
        material = {"event_type": event_type, "payload_hash": payload_hash, "parent_hash": parent}
        chain_hash = hashlib.sha256(self._canonical(material).encode()).hexdigest()
        self.db.execute(
            "INSERT INTO audit_chain(created_at,event_type,payload_hash,parent_hash,chain_hash,payload_json) VALUES(?,?,?,?,?,?)",
            (time.time(), event_type, payload_hash, parent, chain_hash, raw),
        )
        return chain_hash

    def touch(self, status=None):
        now = time.time()
        if status is None:
            self.db.execute("UPDATE case_meta SET updated_at=? WHERE case_id=?", (now, self.case_id))
        else:
            self.db.execute("UPDATE case_meta SET updated_at=?,status=? WHERE case_id=?", (now, str(status), self.case_id))

    def record_observation(self, stage, agent, source, payload, status="RECEIVED", parent_hash=None, metadata=None):
        payload_hash = self._hash(payload)
        self.db.execute(
            "INSERT INTO observations(created_at,stage,agent,source,payload_hash,payload_json,status,parent_hash,metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (time.time(), stage, agent, source, payload_hash, self._canonical(payload), status, parent_hash, self._canonical(dict(metadata or {}))),
        )
        self._append_chain("OBSERVATION", {"stage":stage,"agent":agent,"source":source,"payload_hash":payload_hash,"status":status,"parent_hash":parent_hash})
        self.touch()
        self.db.commit()
        return payload_hash

    def record_trust(self, envelope):
        envelope = dict(envelope or {})
        state = str(envelope.get("state") or "UNKNOWN")
        envelope_hash = str(envelope.get("envelope_hash") or self._hash(envelope))
        self.db.execute(
            "INSERT INTO trust_events(created_at,state,envelope_hash,hard_blocks_json,envelope_json) VALUES(?,?,?,?,?)",
            (time.time(), state, envelope_hash, self._canonical(envelope.get("hard_blocks") or []), self._canonical(envelope)),
        )
        self._append_chain("TRUST", {"state":state,"envelope_hash":envelope_hash})
        self.touch()
        self.db.commit()
        return envelope_hash

    def record_model_run(self, model, market, output, simulations=None, input_payload=None):
        output_hash = self._hash(output)
        input_hash = self._hash(input_payload) if input_payload is not None else None
        self.db.execute(
            "INSERT INTO model_runs(created_at,model,market,simulations,input_hash,output_hash,output_json) VALUES(?,?,?,?,?,?,?)",
            (time.time(), model, market, simulations, input_hash, output_hash, self._canonical(output)),
        )
        self._append_chain("MODEL_RUN", {"model":model,"market":market,"input_hash":input_hash,"output_hash":output_hash})
        self.touch()
        self.db.commit()
        return output_hash

    def record_market(self, market, selection, odds, implied_probability, source, payload):
        payload_hash = self._hash(payload)
        self.db.execute(
            "INSERT INTO market_snapshots(created_at,market,selection,odds,implied_probability,source,payload_hash,payload_json) VALUES(?,?,?,?,?,?,?,?)",
            (time.time(), market, selection, odds, implied_probability, source, payload_hash, self._canonical(payload)),
        )
        self._append_chain("MARKET", {"market":market,"selection":selection,"odds":odds,"payload_hash":payload_hash,"source":source})
        self.touch()
        self.db.commit()
        return payload_hash

    def record_prediction(self, prediction):
        p = dict(prediction or {})
        prediction_id = str(p.get("prediction_id") or self._hash(p))
        if self.db.execute("SELECT 1 FROM predictions WHERE prediction_id=?", (prediction_id,)).fetchone():
            return prediction_id
        self.db.execute(
            "INSERT INTO predictions(prediction_id,created_at,market,selection,probability,odds,edge,expected_value,model,prediction_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (prediction_id,time.time(),p.get("market"),p.get("selection"),p.get("model_probability"),p.get("odds"),p.get("edge"),p.get("expected_value"),p.get("model") or "unknown",self._canonical(p)),
        )
        self._append_chain("PREDICTION", {"prediction_id":prediction_id,"prediction_hash":self._hash(p)})
        self.touch()
        self.db.commit()
        return prediction_id

    def record_arbiter(self, decision):
        d = dict(decision or {})
        state = str(d.get("state") or "UNKNOWN")
        challenge = d.get("challenge") or {}
        blockers = challenge.get("blockers") or []
        warnings = challenge.get("warnings") or []
        decision_hash = self._hash(d)
        self.db.execute(
            "INSERT INTO arbiter_decisions(created_at,state,reason,blockers_json,warnings_json,decision_hash,decision_json) VALUES(?,?,?,?,?,?,?)",
            (time.time(),state,d.get("reason"),self._canonical(blockers),self._canonical(warnings),decision_hash,self._canonical(d)),
        )
        self._append_chain("ARBITER", {"state":state,"decision_hash":decision_hash})
        self.touch("FINAL_QUALIFIED" if state=="FINAL_QUALIFIED" else "REVIEW")
        self.db.commit()
        return decision_hash

    def export_audit_events(self):
        rows=self.db.execute("SELECT sequence,created_at,event_type,payload_hash,parent_hash,chain_hash,payload_json FROM audit_chain ORDER BY sequence").fetchall()
        return [dict(case_id=self.case_id,sequence=r[0],created_at=r[1],event_type=r[2],payload_hash=r[3],parent_hash=r[4],chain_hash=r[5],payload=json.loads(r[6])) for r in rows]

    def record_failure(self, code, severity="BLOCK", evidence=None):
        self.db.execute(
            "INSERT INTO failures(created_at,failure_code,severity,evidence_json) VALUES(?,?,?,?)",
            (time.time(),str(code),str(severity),self._canonical(evidence or {})),
        )
        self._append_chain("FAILURE", {"failure_code":str(code),"severity":str(severity)})
        self.touch("QUARANTINED" if str(severity).upper()=="BLOCK" else "REVIEW")
        self.db.commit()

    def verify_chain(self):
        rows=self.db.execute("SELECT sequence,event_type,payload_hash,parent_hash,chain_hash,payload_json FROM audit_chain ORDER BY sequence").fetchall()
        expected_parent=None; failures=[]
        for sequence,event_type,payload_hash,parent_hash,chain_hash,payload_json in rows:
            actual_payload_hash=hashlib.sha256(self._canonical(json.loads(payload_json)).encode()).hexdigest()
            if actual_payload_hash!=payload_hash: failures.append({"sequence":sequence,"reason":"PAYLOAD_HASH_MISMATCH"})
            if parent_hash!=expected_parent: failures.append({"sequence":sequence,"reason":"PARENT_HASH_MISMATCH"})
            material={"event_type":event_type,"payload_hash":payload_hash,"parent_hash":parent_hash}
            actual_chain=hashlib.sha256(self._canonical(material).encode()).hexdigest()
            if actual_chain!=chain_hash: failures.append({"sequence":sequence,"reason":"CHAIN_HASH_MISMATCH"})
            expected_parent=chain_hash
        return {"valid":not failures,"events":len(rows),"failures":failures,"case_id":self.case_id}

    def summary(self):
        meta=self.db.execute("SELECT case_id,created_at,updated_at,status,schema_version FROM case_meta WHERE case_id=?",(self.case_id,)).fetchone()
        counts={}
        for table in ("observations","trust_events","model_runs","market_snapshots","predictions","arbiter_decisions","failures","audit_chain"):
            counts[table]=self.db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
        last=self.db.execute("SELECT state,decision_hash,created_at FROM arbiter_decisions ORDER BY id DESC LIMIT 1").fetchone()
        return {"case_id":self.case_id,"database":self.path,"status":meta[3] if meta else "UNKNOWN","schema_version":meta[4] if meta else self.VERSION,"created_at":meta[1] if meta else None,"updated_at":meta[2] if meta else None,"counts":counts,"last_arbiter":None if not last else {"state":last[0],"decision_hash":last[1],"created_at":last[2]},"chain":self.verify_chain()}

    def close(self):
        try:self.db.close()
        except Exception:pass


class CaseDatabaseManager:
    VERSION="OMEGA-CASE-DB-MESH-v1"

    def __init__(self, root_dir="case_databases", registry_path=None):
        self.root=Path(root_dir); self.root.mkdir(parents=True,exist_ok=True)
        self.registry_path=Path(registry_path or (self.root/"registry.db"))
        self.registry=sqlite3.connect(str(self.registry_path),check_same_thread=False)
        self.registry.execute("CREATE TABLE IF NOT EXISTS cases(case_id TEXT PRIMARY KEY,db_path TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,status TEXT NOT NULL)")
        self.registry.commit()

    @staticmethod
    def _safe(value):
        value=re.sub(r"[^A-Za-z0-9_.-]+","_",str(value or "unknown"))
        return value[:100] or "unknown"

    @staticmethod
    def _case_filename(case_id):
        digest=hashlib.sha256(str(case_id).encode()).hexdigest()[:16]
        return f"{CaseDatabaseManager._safe(case_id)}_{digest}.db"

    def open(self, case_id):
        cid=str(case_id); path=self.root/self._case_filename(cid); now=time.time()
        self.registry.execute(
            "INSERT INTO cases(case_id,db_path,created_at,updated_at,status) VALUES(?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET updated_at=excluded.updated_at",
            (cid,str(path),now,now,"OPEN"),
        )
        self.registry.commit()
        return CaseDatabase(path,cid)

    def list_cases(self,limit=100):
        rows=self.registry.execute("SELECT case_id,db_path,created_at,updated_at,status FROM cases ORDER BY updated_at DESC LIMIT ?",(max(1,min(1000,int(limit))),)).fetchall()
        return [dict(case_id=r[0],db_path=r[1],created_at=r[2],updated_at=r[3],status=r[4]) for r in rows]

    def close(self):
        try:self.registry.close()
        except Exception:pass
