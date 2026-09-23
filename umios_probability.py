import math, random, re, time
from collections import defaultdict

class UMIOSProbabilityEngine:
    """Independent Poisson + Monte Carlo market engine with conservative edge gates."""
    MARKETS=("1X2","BTTS","TOTAL_GOALS","DOUBLE_CHANCE","DNB","CORRECT_SCORE")

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    @staticmethod
    def _events(history):
        return [e for e in (history or []) if not isinstance(e,dict) or not e.get("error")]

    @classmethod
    def _team_rates(cls,team_id,events,home_team=True):
        gf=[];ga=[]; home_gf=[];home_ga=[];away_gf=[];away_ga=[]
        for e in cls._events(events):
            h=e.get("homeTeam") or {}; a=e.get("awayTeam") or {}
            if str(h.get("id"))==str(team_id):
                hs=cls._num((e.get("homeScore") or {}).get("current",h.get("score")))
                aas=cls._num((e.get("awayScore") or {}).get("current",a.get("score")))
                venue="home"
            elif str(a.get("id"))==str(team_id):
                hs=cls._num((e.get("homeScore") or {}).get("current",h.get("score")))
                aas=cls._num((e.get("awayScore") or {}).get("current",a.get("score")))
                venue="away"
            else: continue
            if hs is None or aas is None: continue
            scored=hs if venue=="home" else aas; conceded=aas if venue=="home" else hs
            gf.append(scored);ga.append(conceded)
            (home_gf if venue=="home" else away_gf).append(scored); (home_ga if venue=="home" else away_ga).append(conceded)
        def mean(x): return sum(x)/len(x) if x else None
        return {"games":len(gf),"gf":mean(gf),"ga":mean(ga),"home_gf":mean(home_gf),"home_ga":mean(home_ga),"away_gf":mean(away_gf),"away_ga":mean(away_ga)}

    @staticmethod
    def _blend(a,b,default):
        vals=[x for x in (a,b) if x is not None]
        return sum(vals)/len(vals) if vals else default

    @staticmethod
    def _poisson_pmf(lam,k):
        return math.exp(-lam)*(lam**k)/math.factorial(k)

    @classmethod
    def _grid(cls,lh,la,max_goals=10):
        ph=[cls._poisson_pmf(lh,k) for k in range(max_goals+1)]
        pa=[cls._poisson_pmf(la,k) for k in range(max_goals+1)]
        grid={(h,a):ph[h]*pa[a] for h in range(max_goals+1) for a in range(max_goals+1)}
        z=sum(grid.values())
        return {k:v/z for k,v in grid.items()}

    @staticmethod
    def _sample_poisson(rng,lam):
        L=math.exp(-lam); k=0; p=1.0
        while p>L:
            k+=1;p*=rng.random()
        return k-1

    @classmethod
    def _monte_carlo(cls,lh,la,n=10000,seed=None):
        rng=random.Random(seed or int(time.time()*1000))
        counts=defaultdict(int)
        for _ in range(n):
            h=cls._sample_poisson(rng,lh); a=cls._sample_poisson(rng,la)
            counts[(h,a)]+=1
        return {k:v/n for k,v in counts.items()}

    @classmethod
    def _market_probs(cls,grid):
        out={"1X2":{},"BTTS":{},"TOTAL_GOALS":{},"DOUBLE_CHANCE":{},"DNB":{},"CORRECT_SCORE":{}}
        out["1X2"]={"1":sum(p for (h,a),p in grid.items() if h>a),"X":sum(p for (h,a),p in grid.items() if h==a),"2":sum(p for (h,a),p in grid.items() if h<a)}
        out["BTTS"]={"YES":sum(p for (h,a),p in grid.items() if h>0 and a>0),"NO":sum(p for (h,a),p in grid.items() if h==0 or a==0)}
        out["DOUBLE_CHANCE"]={"1X":out["1X2"]["1"]+out["1X2"]["X"],"X2":out["1X2"]["X"]+out["1X2"]["2"],"12":out["1X2"]["1"]+out["1X2"]["2"]}
        out["DNB"]={"1":out["1X2"]["1"]/(1-out["1X2"]["X"]),"2":out["1X2"]["2"]/(1-out["1X2"]["X"])}
        for line in (0.5,1.5,2.5,3.5,4.5,5.5):
            out["TOTAL_GOALS"][f"OVER {line}"]=sum(p for (h,a),p in grid.items() if h+a>line)
            out["TOTAL_GOALS"][f"UNDER {line}"]=sum(p for (h,a),p in grid.items() if h+a<line)
        out["CORRECT_SCORE"]={f"{h}-{a}":p for (h,a),p in sorted(grid.items(),key=lambda x:x[1],reverse=True)[:10]}
        return out

    @staticmethod
    def _market_rows(raw_markets):
        rows=[]
        for market,items in raw_markets.items():
            for item in items:
                rows.append((market,item.get("selection"),item.get("implied_probability")))
        return rows

    def run(self,event,evidence,gate,simulations=10000):
        if gate.get("state")!="QUALIFIED": return {"state":"NO_BET","reason":"qualification_gate_blocked","candidates":[]}
        home=event.get("homeTeam") or {}; away=event.get("awayTeam") or {}
        hh=self._team_rates(home.get("id"),(evidence.get("history",{}).get("home") or {}).get("events",[]))
        aa=self._team_rates(away.get("id"),(evidence.get("history",{}).get("away") or {}).get("events",[]))
        # Blend team scoring/conceding rates with conservative league-like priors.
        lh=max(0.15,min(4.5,self._blend(hh["gf"],aa["ga"],1.35)*0.58 + self._blend(hh["home_gf"],aa["away_ga"],1.35)*0.42))
        la=max(0.15,min(4.5,self._blend(aa["gf"],hh["ga"],1.05)*0.58 + self._blend(aa["away_gf"],hh["home_ga"],1.05)*0.42))
        # Shrink aggressively when historical sample is thin.
        sample=min(hh["games"],aa["games"])
        shrink=min(1.0,sample/10.0)
        lh=1.35+(lh-1.35)*shrink; la=1.05+(la-1.05)*shrink
        grid=self._grid(lh,la)
        mc=self._monte_carlo(lh,la,simulations)
        probs=self._market_probs(grid)
        mc_probs=self._market_probs(mc)
        # Ensemble deterministic grid + Monte Carlo estimate.
        ensemble={}
        for market,items in probs.items():
            ensemble[market]={k:round(0.5*v+0.5*mc_probs.get(market,{}).get(k,v),6) for k,v in items.items()}
        market_benchmark=evidence.get("odds") or {}
        candidates=[]
        # Match against de-vigged bookmaker observations produced by UMIOSCoreEngine-like schema.
        observed=[]
        for key,payload in market_benchmark.items():
            if not isinstance(payload,dict): continue
            for m in payload.get("markets",[]) or []:
                name=m.get("name") or m.get("marketName") or ""
                for c in m.get("choices",[]) or []:
                    try: odd=float(c.get("decimalValue") or c.get("odds"))
                    except (TypeError,ValueError): continue
                    if odd>1: observed.append((name,str(c.get("name") or c.get("label") or ""),odd))
        # Independent model is only eligible when it has >=5 completed history games per side.
        history_gate=sample>=5
        for name,selection,odd in observed:
            market="1X2" if ("winner" in name.lower() or name.lower() in {"1x2","match result"}) else "BTTS" if "both teams" in name.lower() else "TOTAL_GOALS" if "over" in name.lower() or "under" in name.lower() or "total" in name.lower() else "OTHER"
            sel=selection.upper().replace("YES","YES").replace("NO","NO")
            p=ensemble.get(market,{}).get(sel)
            if p is None:
                if market=="1X2": p=ensemble["1X2"].get(sel)
            if p is None: continue
            implied=1/odd; edge=p-implied; ev=p*odd-1
            status="QUALIFIED" if history_gate and edge>=0.04 and ev>=0.05 and p>=0.55 else "REJECTED"
            candidates.append({"market":market,"selection":selection,"odds":odd,"model_probability":round(p,4),"market_implied_raw":round(implied,4),"edge":round(edge,4),"expected_value":round(ev,4),"status":status})
        qualified=[x for x in candidates if x["status"]=="QUALIFIED"]
        qualified.sort(key=lambda x:(x["edge"],x["expected_value"]),reverse=True)
        return {"state":"QUALIFIED_PREDICTION" if qualified else "NO_BET","model":"Poisson+MonteCarlo","simulations":simulations,"expected_goals":{"home":round(lh,3),"away":round(la,3)},"history":{"home_games":hh["games"],"away_games":aa["games"],"minimum_games":sample},"probabilities":ensemble,"market_observations":len(observed),"candidates":candidates,"selection":qualified[0] if qualified else None,"generated_at":time.time()}
