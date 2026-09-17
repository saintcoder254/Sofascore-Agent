import re, time, math

class OddsIntelligenceAgent:
    """Converts available bookmaker odds into market-implied probabilities and divergence signals."""
    def __init__(self, store): self.store=store
    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None
    @staticmethod
    def _prob(odds):
        return None if odds is None or odds<=1 else 1.0/odds
    def _markets(self,payload):
        candidates=[]
        def walk(x,path=''):
            if isinstance(x,dict):
                for k,v in x.items():
                    if k.lower() in {'odds','bookmakers','markets','market'}: walk(v,path+'/'+k)
                    elif isinstance(v,(dict,list)): walk(v,path+'/'+k)
            elif isinstance(x,list):
                for v in x: walk(v,path)
        walk(payload)
        return candidates
    def snapshot(self):
        rows=[]
        for row in self.store.current():
            p=row['payload']; odds=p.get('odds') or p.get('markets') or p.get('bookmakers')
            if not odds: continue
            rows.append({'fixture_id':row['fixture_id'],'odds_present':True,'raw_odds':odds,'retrieved_at':row['retrieved_at']})
        return {'generated_at':time.time(),'fixtures_with_odds':len(rows),'items':rows}
    @staticmethod
    def compare(model_probability,odds):
        mp=float(model_probability); op=OddsIntelligenceAgent._prob(OddsIntelligenceAgent._num(odds))
        if op is None:return {'valid':False,'reason':'invalid_odds'}
        return {'valid':True,'odds':float(odds),'market_implied_probability':op,'model_probability':mp,'probability_edge':mp-op,'fair_odds':None if mp<=0 else 1/mp,'expected_value_per_unit':mp*float(odds)-1}
    def status(self):
        s=self.snapshot(); s['principle']='Odds are a benchmark/value layer, never a replacement for match-event truth.'; return s
