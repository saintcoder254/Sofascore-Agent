import re, time
from collections import defaultdict

class UMIOSCoreEngine:
    """Evidence-to-market layer. Missing independent model evidence is never fabricated."""
    def __init__(self, odds_agent=None): self.odds_agent = odds_agent
    @staticmethod
    def _num(v):
        try:
            if isinstance(v, str): v=v.replace('%','').replace(',','').strip()
            return float(v)
        except (TypeError,ValueError): return None
    @classmethod
    def _walk_stats(cls,obj,out=None):
        out=out if out is not None else defaultdict(list)
        if isinstance(obj,dict):
            for k,v in obj.items():
                if isinstance(v,(dict,list)): cls._walk_stats(v,out)
                else:
                    n=cls._num(v)
                    if n is not None:
                        key=re.sub(r'[^a-z0-9]+','_',str(k).lower()).strip('_')
                        if key: out[key].append(n)
        elif isinstance(obj,list):
            for v in obj: cls._walk_stats(v,out)
        return out
    @classmethod
    def _odds_rows(cls,payload):
        rows=[]; seen=set()
        def walk(x,hint=''):
            if isinstance(x,dict):
                h=next((str(x[k]) for k in ('marketName','name','market','marketNameText') if x.get(k)),hint)
                choices=x.get('choices')
                if isinstance(choices,list):
                    for c in choices:
                        if not isinstance(c,dict): continue
                        odd=cls._num(c.get('decimalValue') or c.get('odds') or c.get('fractionalValue'))
                        name=c.get('name') or c.get('label') or c.get('choiceName')
                        if odd and odd>1 and name:
                            key=(h.lower(),str(name).lower(),round(odd,5))
                            if key not in seen: seen.add(key); rows.append({'market':h,'selection':str(name),'odds':odd})
                for k,v in x.items():
                    if k!='choices' and isinstance(v,(dict,list)): walk(v,h)
            elif isinstance(x,list):
                for v in x: walk(v,hint)
        walk(payload); return rows
    @staticmethod
    def _market(text):
        s=re.sub(r'[^a-z0-9]+',' ',str(text or '').lower()).strip()
        if 'match winner' in s or s in {'winner','1x2','full time result'}: return '1X2'
        if 'both teams' in s and 'score' in s: return 'BTTS'
        if 'over under' in s or 'total goals' in s or s in {'goals','o u'}: return 'TOTAL_GOALS'
        if 'double chance' in s: return 'DOUBLE_CHANCE'
        if 'draw no bet' in s or s=='dnb': return 'DNB'
        if 'handicap' in s: return 'HANDICAP'
        if 'corner' in s: return 'CORNERS'
        if 'card' in s: return 'CARDS'
        return 'OTHER'
    @staticmethod
    def _devig(rows):
        valid=[r for r in rows if r.get('odds',0)>1]
        z=sum(1/r['odds'] for r in valid)
        if len(valid)<2 or z<=0: return []
        return [{**r,'implied_probability':round((1/r['odds'])/z,6)} for r in valid]
    def build_features(self,fixture,evidence):
        event=evidence.get('event') or fixture or {}; home=event.get('homeTeam') or {}; away=event.get('awayTeam') or {}
        stats=self._walk_stats(evidence.get('statistics') or {})
        incidents=evidence.get('incidents') or {}; shotmap=evidence.get('shotmap') or {}; lineup=evidence.get('lineups') or {}
        verification=evidence.get('verification') or {}; odds=self._odds_rows(evidence.get('odds') or {})
        grouped=defaultdict(list)
        for r in odds: grouped[self._market(r['market'])].append(r)
        markets={k:self._devig(v) for k,v in grouped.items() if len(v)>=2}
        features={'home_team':home.get('name'),'away_team':away.get('name'),'home_score':self._num(home.get('score')),'away_score':self._num(away.get('score')),'event_status':((event.get('status') or {}).get('type') or {}).get('state'),'stat_keys':len(stats),'stat_observations':sum(len(v) for v in stats.values()),'incident_observations':len(incidents.get('incidents') or incidents.get('events') or []) if isinstance(incidents,dict) else 0,'shot_observations':len(shotmap.get('shots') or []) if isinstance(shotmap,dict) else 0,'lineup_signal':bool(lineup.get('home') or lineup.get('away') or lineup.get('homeTeam') or lineup.get('awayTeam')),'odds_observations':len(odds),'retrieved_at':evidence.get('retrieved_at'),'numeric_stats':{k:{'min':min(v),'max':max(v),'mean':sum(v)/len(v)} for k,v in stats.items() if v}}
        return features,markets
    def analyze(self,fixture,evidence,gate):
        features,markets=self.build_features(fixture,evidence)
        if gate.get('state')!='QUALIFIED': return {'state':'NO_BET','reason':'qualification_gate_blocked','features':features,'markets':markets,'candidates':[],'generated_at':time.time()}
        candidates=[]
        for market,rows in markets.items():
            if market not in {'1X2','BTTS','TOTAL_GOALS','DOUBLE_CHANCE','DNB','HANDICAP','CORNERS','CARDS'}: continue
            for r in rows: candidates.append({'market':market,'selection':r['selection'],'odds':r['odds'],'market_probability':r['implied_probability'],'model_probability':None,'edge':None,'status':'BENCHMARK_ONLY','reason':'No trained independent probability model is connected yet.'})
        return {'state':'ANALYZED','features':features,'markets':markets,'candidates':candidates,'generated_at':time.time()}
