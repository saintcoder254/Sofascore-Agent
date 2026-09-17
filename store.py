import sqlite3, json, time

class Store:
    def __init__(self,path):
        self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS snapshots(fixture_id TEXT NOT NULL,retrieved_at REAL NOT NULL,payload_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(fixture_id,retrieved_at))')
        self.db.execute('CREATE TABLE IF NOT EXISTS current(fixture_id TEXT PRIMARY KEY,retrieved_at REAL NOT NULL,payload_hash TEXT NOT NULL,payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS predictions(prediction_id TEXT PRIMARY KEY,fixture_id TEXT NOT NULL,market TEXT NOT NULL,predicted_probability REAL NOT NULL,selection TEXT,odds REAL,predicted_at REAL NOT NULL,outcome REAL,outcome_at REAL,model_version TEXT NOT NULL,features_json TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS evolution_runs(run_id TEXT PRIMARY KEY,created_at REAL NOT NULL,result_json TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS evolution_candidates(candidate_id TEXT PRIMARY KEY,created_at REAL NOT NULL,candidate_json TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS external_observations(id INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL,retrieved_at REAL NOT NULL,fixture_key TEXT NOT NULL,home TEXT,away TEXT,kickoff TEXT,market TEXT,selection TEXT,raw_json TEXT NOT NULL,outcome REAL,outcome_at REAL)')
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_external_dedupe ON external_observations(source,fixture_key,kickoff,market,selection)')
        self.db.commit()
    def get_current(self,fixture_id):
        r=self.db.execute('SELECT retrieved_at,payload_hash,payload FROM current WHERE fixture_id=?',(fixture_id,)).fetchone(); return None if not r else {'retrieved_at':r[0],'payload_hash':r[1],'payload':json.loads(r[2])}
    def put(self,fixture_id,retrieved_at,payload_hash,payload):
        raw=json.dumps(payload,separators=(',',':')); self.db.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?)',(str(fixture_id),retrieved_at,payload_hash,raw)); self.db.execute('INSERT OR REPLACE INTO current VALUES(?,?,?,?)',(str(fixture_id),retrieved_at,payload_hash,raw)); self.db.commit()
    def current(self): return [{'fixture_id':r[0],'retrieved_at':r[1],'payload_hash':r[2],'payload':json.loads(r[3])} for r in self.db.execute('SELECT fixture_id,retrieved_at,payload_hash,payload FROM current').fetchall()]
    def add_prediction(self,prediction_id,fixture_id,market,predicted_probability,selection=None,odds=None,predicted_at=None,model_version='unknown',features=None):
        self.db.execute('INSERT OR REPLACE INTO predictions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(prediction_id,str(fixture_id),market,float(predicted_probability),selection,None if odds is None else float(odds),predicted_at or time.time(),None,None,model_version,json.dumps(features or {},separators=(',',':')))); self.db.commit()
    def record_outcome(self,prediction_id,outcome,outcome_at=None): self.db.execute('UPDATE predictions SET outcome=?,outcome_at=? WHERE prediction_id=?',(float(outcome),outcome_at or time.time(),prediction_id)); self.db.commit()
    def predictions_with_outcomes(self):
        rows=self.db.execute('SELECT prediction_id,fixture_id,market,predicted_probability,selection,odds,predicted_at,outcome,outcome_at,model_version,features_json FROM predictions WHERE outcome IS NOT NULL').fetchall(); return [dict(prediction_id=r[0],fixture_id=r[1],market=r[2],predicted_probability=r[3],selection=r[4],odds=r[5],predicted_at=r[6],outcome=r[7],outcome_at=r[8],model_version=r[9],features=json.loads(r[10] or '{}')) for r in rows]
    def pending_predictions(self):
        rows=self.db.execute('SELECT prediction_id,fixture_id,market,predicted_probability,selection,odds,predicted_at,outcome,outcome_at,model_version,features_json FROM predictions WHERE outcome IS NULL').fetchall(); return [dict(prediction_id=r[0],fixture_id=r[1],market=r[2],predicted_probability=r[3],selection=r[4],odds=r[5],predicted_at=r[6],outcome=r[7],outcome_at=r[8],model_version=r[9],features=json.loads(r[10] or '{}')) for r in rows]
    def prediction_count(self): return self.db.execute('SELECT COUNT(*) FROM predictions').fetchone()[0]
    def resolved_prediction_count(self): return self.db.execute('SELECT COUNT(*) FROM predictions WHERE outcome IS NOT NULL').fetchone()[0]
    def performance_summary(self):
        rows=self.predictions_with_outcomes()
        if not rows:return {'samples':0,'wins':0,'losses':0,'pushes':0,'brier':None,'roi':None,'profit_units':0.0,'markets':{}}
        brier=sum((r['predicted_probability']-r['outcome'])**2 for r in rows)/len(rows); wins=sum(r['outcome']==1.0 for r in rows); losses=sum(r['outcome']==0.0 for r in rows); pushes=len(rows)-wins-losses; profit=staked=0.0; markets={}
        for r in rows:
            if r['odds'] and r['odds']>1: staked+=1; profit+=(r['odds']-1) if r['outcome']==1 else -1 if r['outcome']==0 else 0
            b=markets.setdefault(str(r['market']),{'samples':0,'wins':0,'losses':0,'brier':0.0}); b['samples']+=1; b['wins']+=int(r['outcome']==1); b['losses']+=int(r['outcome']==0); b['brier']+=(r['predicted_probability']-r['outcome'])**2
        for b in markets.values(): b['brier']/=b['samples']
        return {'samples':len(rows),'wins':wins,'losses':losses,'pushes':pushes,'brier':brier,'roi':None if not staked else profit/staked,'profit_units':profit,'markets':markets}
    @staticmethod
    def external_fixture_key(home,away): return f'{str(home).strip().lower()}::{str(away).strip().lower()}'
    def add_external_observations(self,source,observations,retrieved_at=None):
        ts=retrieved_at or time.time(); added=0
        for obs in observations or []:
            h,a=obs.get('home'),obs.get('away')
            if not h or not a: continue
            raw=dict(obs); raw.setdefault('source',source)
            params=(source,self.external_fixture_key(h,a),obs.get('kickoff_local'),obs.get('market'),obs.get('prediction'))
            exists=self.db.execute('SELECT id FROM external_observations WHERE source=? AND fixture_key=? AND kickoff IS ? AND market IS ? AND selection IS ? LIMIT 1',params).fetchone()
            if exists: continue
            self.db.execute('INSERT OR IGNORE INTO external_observations(source,retrieved_at,fixture_key,home,away,kickoff,market,selection,raw_json,outcome,outcome_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(source,ts,self.external_fixture_key(h,a),h,a,obs.get('kickoff_local'),obs.get('market'),obs.get('prediction'),json.dumps(raw,separators=(',',':')),None,None)); added+=1
        self.db.commit(); return added
    def external_summary(self,source=None):
        where='' if source is None else ' WHERE source=?'; args=() if source is None else (source,); count=self.db.execute('SELECT COUNT(*) FROM external_observations'+where,args).fetchone()[0]; latest=self.db.execute('SELECT MAX(retrieved_at) FROM external_observations'+where,args).fetchone()[0]; resolved=self.db.execute('SELECT COUNT(*) FROM external_observations'+where+(' AND outcome IS NOT NULL' if where else ' WHERE outcome IS NOT NULL'),args).fetchone()[0]; return {'source':source or 'all','observations':count,'resolved':resolved,'latest_at':latest}
    def external_pending(self):
        rows=self.db.execute('SELECT id,source,retrieved_at,fixture_key,home,away,kickoff,market,selection,raw_json FROM external_observations WHERE outcome IS NULL').fetchall(); return [dict(id=r[0],source=r[1],retrieved_at=r[2],fixture_key=r[3],home=r[4],away=r[5],kickoff=r[6],market=r[7],selection=r[8],raw=json.loads(r[9] or '{}')) for r in rows]
    def resolved_external_observations(self):
        rows=self.db.execute('SELECT id,source,retrieved_at,fixture_key,home,away,kickoff,market,selection,raw_json,outcome,outcome_at FROM external_observations WHERE outcome IS NOT NULL').fetchall(); return [dict(id=r[0],source=r[1],retrieved_at=r[2],fixture_key=r[3],home=r[4],away=r[5],kickoff=r[6],market=r[7],selection=r[8],raw=json.loads(r[9] or '{}'),outcome=r[10],outcome_at=r[11]) for r in rows]
    def record_external_outcome(self,obs_id,outcome,outcome_at=None): self.db.execute('UPDATE external_observations SET outcome=?,outcome_at=? WHERE id=?',(float(outcome),outcome_at or time.time(),obs_id)); self.db.commit()
    def find_current_fixture(self,home,away):
        h,a=str(home or '').lower().strip(),str(away or '').lower().strip()
        for row in self.current():
            p=row['payload']; ph=str((p.get('homeTeam') or {}).get('name') or '').lower().strip(); pa=str((p.get('awayTeam') or {}).get('name') or '').lower().strip()
            if ph==h and pa==a:return row
        return None
    @staticmethod
    def fixture_has_conflict(payload): return bool(payload.get('verification_conflicts')) or bool((payload.get('verification') or {}).get('conflict'))
    @staticmethod
    def final_result(payload):
        st=(payload.get('status') or {}).get('type') or {}; state=str(st.get('state','')).lower()
        if state in {'cancelled','canceled','postponed','abandoned','suspended'} or (state not in {'post','final','finished','completed'} and not st.get('completed')):return None
        try:h=int(float((payload.get('homeTeam') or {}).get('score')));a=int(float((payload.get('awayTeam') or {}).get('score')))
        except (TypeError,ValueError):return None
        return {'home':h,'away':a,'result':'HOME' if h>a else 'AWAY' if h<a else 'DRAW'}
    def source_score(self,source,market,competition):
        try:r=self.db.execute('SELECT samples,wins,accuracy,brier,avg_probability,weight,status,updated_at FROM source_scores WHERE source=? AND market=? AND competition=?',(source,market,competition)).fetchone()
        except sqlite3.OperationalError:return None
        return None if not r else dict(samples=r[0],wins=r[1],accuracy=r[2],brier=r[3],avg_probability=r[4],weight=r[5],status=r[6],updated_at=r[7])
    def upsert_source_score(self,source,market,competition,samples,accuracy,brier,avg_probability,weight,status):
        self.db.execute('CREATE TABLE IF NOT EXISTS source_scores(source TEXT NOT NULL,market TEXT NOT NULL,competition TEXT NOT NULL,samples INTEGER NOT NULL,wins REAL NOT NULL,accuracy REAL,brier REAL,avg_probability REAL,weight REAL NOT NULL,status TEXT NOT NULL,updated_at REAL NOT NULL,PRIMARY KEY(source,market,competition))'); self.db.execute('INSERT OR REPLACE INTO source_scores VALUES(?,?,?,?,?,?,?,?,?,?,?)',(source,market,competition,int(samples),float(samples*accuracy),float(accuracy),brier,avg_probability,float(weight),status,time.time())); self.db.commit()
    def add_source_weight_history(self,source,market,competition,weight,status,reason):
        self.db.execute('CREATE TABLE IF NOT EXISTS source_weight_history(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at REAL NOT NULL,source TEXT NOT NULL,market TEXT NOT NULL,competition TEXT NOT NULL,weight REAL NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL)'); self.db.execute('INSERT INTO source_weight_history(created_at,source,market,competition,weight,status,reason) VALUES(?,?,?,?,?,?,?)',(time.time(),source,market,competition,float(weight),status,reason)); self.db.commit()
    def source_scores(self,source=None):
        try:q='SELECT source,market,competition,samples,accuracy,brier,avg_probability,weight,status,updated_at FROM source_scores';
        except Exception:return []
        args=()
        if source:q+=' WHERE source=?';args=(source,)
        try:return [dict(source=r[0],market=r[1],competition=r[2],samples=r[3],accuracy=r[4],brier=r[5],avg_probability=r[6],weight=r[7],status=r[8],updated_at=r[9]) for r in self.db.execute(q,args).fetchall()]
        except sqlite3.OperationalError:return []
    def add_evolution_run(self,run_id,result): self.db.execute('INSERT OR REPLACE INTO evolution_runs VALUES(?,?,?)',(run_id,time.time(),json.dumps(result,separators=(',',':'))));self.db.commit()
    def latest_evolution_run(self):
        r=self.db.execute('SELECT result_json FROM evolution_runs ORDER BY created_at DESC LIMIT 1').fetchone();return json.loads(r[0]) if r else None
    def add_candidate(self,candidate):self.db.execute('INSERT OR REPLACE INTO evolution_candidates VALUES(?,?,?)',(candidate['candidate_id'],candidate.get('created_at',time.time()),json.dumps(candidate,separators=(',',':'))));self.db.commit()
    def latest_candidates(self,limit=20):return [json.loads(r[0]) for r in self.db.execute('SELECT candidate_json FROM evolution_candidates ORDER BY created_at DESC LIMIT ?',(int(limit),)).fetchall()]
