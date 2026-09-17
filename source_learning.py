import json, re, time
from collections import defaultdict

class SourceLearningAgent:
    """Scores external forecasters and keeps them in shadow mode until enough evidence exists."""
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
    @staticmethod
    def result(payload):
        s=(payload.get('status') or {}).get('type') or {}; state=str(s.get('state','')).lower()
        if state in {'cancelled','canceled','postponed','abandoned','suspended'} or (state not in {'post','final','finished','completed'} and not s.get('completed')):return None
        try:h=int(float((payload.get('homeTeam') or {}).get('score'))); a=int(float((payload.get('awayTeam') or {}).get('score')))
        except (TypeError,ValueError):return None
        return h,a
    def settle(self,obs,h,a):
        m=self.market(obs.get('market'),obs.get('selection')); s=str(obs.get('selection') or '').lower().strip(); total=h+a
        if m=='1x2': return float(h>a) if s in {'1','home','home win'} else float(h==a) if s in {'x','draw'} else float(a>h) if s in {'2','away','away win'} else None
        if m=='double_chance': return float(h>=a) if '1x' in s or 'home or draw' in s else float(a>=h) if 'x2' in s or 'draw or away' in s else float(h!=a) if '12' in s or 'home or away' in s else None
        if m=='btts':
            yes=h>0 and a>0; return float(yes) if ('yes' in s or 'gg' in s) else float(not yes) if ('no' in s or 'ng' in s) else None
        if m=='goals_ou':
            z=re.search(r'([+-]?\d+(?:\.\d+)?)',s)
            if not z:return None
            line=float(z.group(1)); over='over' in s or s.startswith('o'); under='under' in s or s.startswith('u')
            if not(over or under):return None
            return 1.0 if (total>line and over) or (total<line and under) else 0.0 if (total<line and over) or (total>line and under) else 0.5
        if m=='correct_score':
            z=re.search(r'(\d+)\s*[-:]\s*(\d+)',s); return float(h==int(z.group(1)) and a==int(z.group(2))) if z else None
        return None
    def _rows(self, resolved=False):
        q='SELECT id,source,retrieved_at,home,away,market,selection,raw_json,outcome FROM external_observations'
        if resolved:q+=' WHERE outcome IS NOT NULL'
        else:q+=' WHERE outcome IS NULL'
        rows=self.store.db.execute(q).fetchall(); out=[]
        for r in rows:out.append({'id':r[0],'source':r[1],'retrieved_at':r[2],'home':r[3],'away':r[4],'market':r[5],'selection':r[6],'raw':json.loads(r[7] or '{}'),'outcome':r[8]})
        return out
    def _fixture(self,home,away):
        h=str(home or '').lower().strip(); a=str(away or '').lower().strip()
        for row in self.store.current():
            p=row['payload']; ph=str((p.get('homeTeam') or {}).get('name') or '').lower().strip(); pa=str((p.get('awayTeam') or {}).get('name') or '').lower().strip()
            if ph==h and pa==a:return p
    def resolve(self):
        resolved=blocked=unresolved=0
        for o in self._rows():
            p=self._fixture(o['home'],o['away'])
            if not p:unresolved+=1;continue
            if (p.get('verification') or {}).get('conflict') or p.get('verification_conflicts'):blocked+=1;continue
            r=self.result(p)
            if not r:unresolved+=1;continue
            outcome=self.settle(o,*r)
            if outcome is None:unresolved+=1;continue
            self.store.db.execute('UPDATE external_observations SET outcome=?,outcome_at=? WHERE id=?',(outcome,time.time(),o['id']));resolved+=1
        self.store.db.commit();return {'resolved':resolved,'unresolved':unresolved,'blocked_conflicts':blocked}
    @staticmethod
    def probability(o):
        for k in ('probability','predicted_probability','confidence'):
            try:v=float(o['raw'].get(k,o.get(k))); v=v/100 if v>1 else v; return v if 0<=v<=1 else None
            except (TypeError,ValueError):pass
        return None
    def score(self):
        groups=defaultdict(list)
        for o in self._rows(True):groups[(o['source'],self.market(o['market'],o['selection']),str(o['raw'].get('competition') or 'unknown').lower())].append(o)
        out=[]
        for (src,mkt,comp),rows in groups.items():
            n=len(rows); acc=sum(r['outcome']==1 for r in rows)/n; pairs=[(self.probability(r),r) for r in rows]; known=[x for x in pairs if x[0] is not None]; brier=sum((p-r['outcome'])**2 for p,r in known)/len(known) if known else None
            old=self.store.db.execute('SELECT weight FROM source_scores WHERE source=? AND market=? AND competition=?',(src,mkt,comp)).fetchone(); weight=float(old[0]) if old else 1.0; status='SHADOW_TEST_REQUIRED' if n<self.min_samples else 'EVALUATED'
            if n>=self.min_samples:weight=max(.5,min(1.5,.75+.5*acc))
            self.store.db.execute('INSERT OR REPLACE INTO source_scores VALUES(?,?,?,?,?,?,?,?,?,?,?)',(src,mkt,comp,n,acc*n,acc,brier,sum(p for p,_ in known)/len(known) if known else None,weight,status,time.time())); self.store.db.execute('INSERT INTO source_weight_history(created_at,source,market,competition,weight,status,reason) VALUES(?,?,?,?,?,?,?)',(time.time(),src,mkt,comp,weight,status,f'samples={n};accuracy={acc:.4f}')); out.append({'source':src,'market':mkt,'competition':comp,'samples':n,'accuracy':acc,'brier':brier,'weight':weight,'status':status})
        self.store.db.commit();return out
    def status(self):return [{'source':r[0],'market':r[1],'competition':r[2],'samples':r[3],'accuracy':r[4],'brier':r[5],'weight':r[7],'status':r[8],'updated_at':r[9]} for r in self.store.db.execute('SELECT source,market,competition,samples,accuracy,brier,avg_probability,weight,status,updated_at FROM source_scores').fetchall()]
    def run(self):return {'created_at':time.time(),'resolution':self.resolve(),'scores':self.score(),'min_samples':self.min_samples}
