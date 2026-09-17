import json, re, time
from collections import defaultdict

class SourceLearningAgent:
    """Scores external forecasters only after the independent verification agent settles results."""
    def __init__(self, store, min_samples=100):
        self.store=store; self.min_samples=int(min_samples or 100); self._schema()
    def _schema(self):
        self.store.db.execute('''CREATE TABLE IF NOT EXISTS source_scores(source TEXT NOT NULL, market TEXT NOT NULL, competition TEXT NOT NULL, samples INTEGER NOT NULL, wins REAL NOT NULL, accuracy REAL, brier REAL, avg_probability REAL, weight REAL NOT NULL, status TEXT NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY(source,market,competition))''')
        self.store.db.execute('''CREATE TABLE IF NOT EXISTS source_weight_history(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL NOT NULL, source TEXT NOT NULL, market TEXT NOT NULL, competition TEXT NOT NULL, weight REAL NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL)'''); self.store.db.commit()
    @staticmethod
    def market(market,selection):
        m=re.sub(r'[^a-z0-9]+',' ',str(market or '').lower()).strip(); s=str(selection or '').lower()
        if 'btts' in m or 'both teams' in m or s in {'gg','ng'}: return 'btts'
        if 'correct' in m and 'score' in m:return 'correct_score'
        if 'double' in m:return 'double_chance'
        if 'handicap' in m:return 'handicap'
        if 'dnb' in m or 'draw no bet' in m:return 'dnb'
        if 'over' in m or 'under' in m or 'total' in m:return 'goals_ou'
        if 'winner' in m or m in {'1x2','match winner','moneyline'}:return '1x2'
        return m or 'unknown'
    def _rows(self):
        rows=self.store.db.execute('SELECT id,source,retrieved_at,home,away,market,selection,raw_json,outcome FROM external_observations WHERE outcome IS NOT NULL').fetchall()
        return [{'id':r[0],'source':r[1],'retrieved_at':r[2],'home':r[3],'away':r[4],'market':r[5],'selection':r[6],'raw':json.loads(r[7] or '{}'),'outcome':r[8]} for r in rows]
    @staticmethod
    def probability(o):
        for k in ('probability','predicted_probability','confidence'):
            try:
                v=float(o['raw'].get(k,o.get(k))); v=v/100 if v>1 else v
                return v if 0<=v<=1 else None
            except (TypeError,ValueError): pass
        return None
    def score(self):
        groups=defaultdict(list)
        for o in self._rows():groups[(o['source'],self.market(o['market'],o['selection']),str(o['raw'].get('competition') or 'unknown').lower())].append(o)
        out=[]
        for (src,mkt,comp),rows in groups.items():
            n=len(rows); acc=sum(r['outcome']==1 for r in rows)/n
            known=[(self.probability(r),r) for r in rows if self.probability(r) is not None]
            brier=sum((p-r['outcome'])**2 for p,r in known)/len(known) if known else None
            old=self.store.db.execute('SELECT weight FROM source_scores WHERE source=? AND market=? AND competition=?',(src,mkt,comp)).fetchone()
            weight=float(old[0]) if old else 1.0
            status='SHADOW_TEST_REQUIRED' if n<self.min_samples else 'EVALUATED'
            if n>=self.min_samples: weight=max(.5,min(1.5,.75+.5*acc))
            self.store.db.execute('INSERT OR REPLACE INTO source_scores VALUES(?,?,?,?,?,?,?,?,?,?,?)',(src,mkt,comp,n,acc*n,acc,brier,sum(p for p,_ in known)/len(known) if known else None,weight,status,time.time()))
            self.store.db.execute('INSERT INTO source_weight_history(created_at,source,market,competition,weight,status,reason) VALUES(?,?,?,?,?,?,?)',(time.time(),src,mkt,comp,weight,status,f'samples={n};accuracy={acc:.4f}'))
            out.append({'source':src,'market':mkt,'competition':comp,'samples':n,'accuracy':acc,'brier':brier,'weight':weight,'status':status})
        self.store.db.commit();return out
    def status(self):return [{'source':r[0],'market':r[1],'competition':r[2],'samples':r[3],'accuracy':r[4],'brier':r[5],'weight':r[7],'status':r[8],'updated_at':r[9]} for r in self.store.db.execute('SELECT source,market,competition,samples,accuracy,brier,avg_probability,weight,status,updated_at FROM source_scores').fetchall()]
    def run(self):return {'created_at':time.time(),'resolution':{'resolved':0,'note':'Settlement is gated by independent verification consensus'},'scores':self.score(),'min_samples':self.min_samples}
