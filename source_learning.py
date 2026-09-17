import json, math, re, time, hashlib
from collections import defaultdict

class SourceLearningAgent:
    """Learns whether external forecasters add measurable signal without promoting them automatically."""
    MIN_SAMPLES = 100

    def __init__(self, store, min_samples=100):
        self.store = store
        self.min_samples = int(min_samples or self.MIN_SAMPLES)
        self._ensure_schema()

    def _ensure_schema(self):
        db = self.store.db
        db.execute('''CREATE TABLE IF NOT EXISTS source_scores(
            source TEXT NOT NULL, market TEXT NOT NULL, competition TEXT NOT NULL,
            samples INTEGER NOT NULL, wins REAL NOT NULL, accuracy REAL,
            brier REAL, avg_probability REAL, weight REAL NOT NULL,
            status TEXT NOT NULL, updated_at REAL NOT NULL,
            PRIMARY KEY(source, market, competition))''')
        db.execute('''CREATE TABLE IF NOT EXISTS source_weight_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL NOT NULL,
            source TEXT NOT NULL, market TEXT NOT NULL, competition TEXT NOT NULL,
            weight REAL NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL)''')
        db.commit()

    @staticmethod
    def normalize_market(market, selection):
        m = re.sub(r'[^a-z0-9]+', ' ', str(market or '').lower()).strip()
        s = str(selection or '').lower()
        if 'btts' in m or 'both teams' in m or s in {'gg','ng'}: return 'btts'
        if 'correct' in m and 'score' in m: return 'correct_score'
        if 'double' in m: return 'double_chance'
        if 'handicap' in m: return 'handicap'
        if 'dnb' in m or 'draw no bet' in m: return 'dnb'
        if 'over' in m or 'under' in m or 'total' in m: return 'goals_ou'
        if 'winner' in m or m in {'1x2','match winner','moneyline'}: return '1x2'
        return m or 'unknown'

    @staticmethod
    def _fixture_match(home, away, row):
        a, b = str(home or '').lower(), str(away or '').lower()
        return a == str(row.get('home') or '').lower() and b == str(row.get('away') or '').lower()

    @staticmethod
    def _extract_competition(obs):
        raw = obs.get('raw') or obs.get('raw_json') or {}
        if isinstance(raw, str):
            try: raw = json.loads(raw)
            except Exception: raw = {}
        return str(obs.get('competition') or raw.get('competition') or 'unknown').strip().lower()

    @staticmethod
    def _selection_probability(obs):
        for key in ('probability','predicted_probability','confidence'):
            try:
                value=float(obs.get(key));
                if value > 1: value /= 100
                if 0 <= value <= 1: return value
            except (TypeError, ValueError): pass
        return None

    def _settle_observation(self, obs, result):
        market=self.normalize_market(obs.get('market'), obs.get('prediction') or obs.get('selection'))
        selection=str(obs.get('prediction') or obs.get('selection') or '').lower().strip()
        h,a=result['home'],result['away']; total=h+a
        if market=='1x2':
            if selection in {'1','home','home win'}: return float(h>a)
            if selection in {'x','draw'}: return float(h==a)
            if selection in {'2','away','away win'}: return float(a>h)
        if market=='double_chance':
            if '1x' in selection or 'home or draw' in selection: return float(h>=a)
            if 'x2' in selection or 'draw or away' in selection: return float(a>=h)
            if '12' in selection or 'home or away' in selection: return float(h!=a)
        if market=='btts':
            yes=h>0 and a>0
            return float(yes) if any(x in selection for x in ('yes','gg')) else float(not yes) if any(x in selection for x in ('no','ng')) else None
        if market=='goals_ou':
            match=re.search(r'([+-]?\d+(?:\.\d+)?)',selection)
            if not match: return None
            line=float(match.group(1)); over='over' in selection or selection.startswith('o'); under='under' in selection or selection.startswith('u')
            if not (over or under): return None
            return 1.0 if total>line and over or total<line and under else 0.0 if total<line and over or total>line and under else 0.5
        if market=='correct_score':
            match=re.search(r'(\d+)\s*[-:]\s*(\d+)',selection)
            return float(h==int(match.group(1)) and a==int(match.group(2))) if match else None
        return None

    def resolve(self):
        """Resolve stored external observations against cached completed fixtures when safely matchable."""
        resolved=blocked=unresolved=0
        rows=self.store.external_pending()
        for obs in rows:
            fixture=self.store.find_current_fixture(obs.get('home'), obs.get('away'))
            if not fixture: unresolved+=1; continue
            payload=fixture['payload']
            if self.store.fixture_has_conflict(payload): blocked+=1; continue
            result=self.store.final_result(payload)
            if not result: unresolved+=1; continue
            outcome=self._settle_observation(obs,result)
            if outcome is None: unresolved+=1; continue
            self.store.record_external_outcome(obs['id'], outcome, time.time()); resolved+=1
        return {'resolved':resolved,'unresolved':unresolved,'blocked_conflicts':blocked}

    def score(self):
        groups=defaultdict(list)
        for obs in self.store.resolved_external_observations():
            market=self.normalize_market(obs.get('market'),obs.get('selection'))
            comp=self._extract_competition(obs)
            groups[(obs['source'],market,comp)].append(obs)
        results=[]
        for (source,market,comp), rows in groups.items():
            n=len(rows); wins=sum(float(r['outcome']==1) for r in rows)
            probs=[self._selection_probability(r) for r in rows]; known=[(p,r) for p,r in zip(probs,rows) if p is not None]
            brier=sum((p-r['outcome'])**2 for p,r in known)/len(known) if known else None
            accuracy=wins/n
            old=self.store.source_score(source,market,comp)
            weight=float(old['weight']) if old else 1.0
            status='SHADOW_TEST_REQUIRED' if n < self.min_samples else 'EVALUATED'
            if n >= self.min_samples:
                # Conservative evidence adjustment around a neutral 1.0 source weight.
                weight=max(0.5,min(1.5,0.75 + accuracy*0.5))
            self.store.upsert_source_score(source,market,comp,n,wins/n,brier,(sum(p for p,_ in known)/len(known) if known else None),weight,status)
            self.store.add_source_weight_history(source,market,comp,weight,status,f'samples={n};accuracy={accuracy:.4f}')
            results.append({'source':source,'market':market,'competition':comp,'samples':n,'accuracy':accuracy,'brier':brier,'weight':weight,'status':status})
        return results

    def run(self):
        resolution=self.resolve(); scores=self.score()
        return {'created_at':time.time(),'resolution':resolution,'scores':scores,'promotion_policy':f'No source weight changes are eligible before {self.min_samples} resolved samples per source/market/competition bucket.'}
