"""Empirical + hybrid football goal distribution engine for Elite MatchMaster OMEGA."""
import math, random, time
from collections import Counter

class EmpiricalGoalEngine:
    VERSION = "OMEGA-EMPIRICAL-HYBRID-v1"

    def __init__(self, simulations=250000, seed=42):
        self.simulations = max(10000, min(int(simulations), 2000000))
        self.seed = seed

    @staticmethod
    def _finished(e):
        st=((e.get("status") or {}).get("type") or {}) if isinstance(e,dict) else {}
        return str(st.get("state") or "").lower() in {"post","final","finished","completed","ended","after_penalties","after_extra_time"} or st.get("completed") is True

    @staticmethod
    def _score(e):
        try:
            return int((e.get("homeScore") or {}).get("current")), int((e.get("awayScore") or {}).get("current"))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _team_samples(cls, team_id, events, venue):
        rows=[]
        for e in events or []:
            if not cls._finished(e): continue
            score=cls._score(e)
            if score is None: continue
            h=e.get("homeTeam") or {}; a=e.get("awayTeam") or {}
            if venue=="home" and str(h.get("id"))==str(team_id): rows.append((score[0],score[1]))
            elif venue=="away" and str(a.get("id"))==str(team_id): rows.append((score[1],score[0]))
        return rows

    @staticmethod
    def _weighted_choice(rng, values, decay=0.88):
        if not values: return None
        return rng.choices(values, weights=[decay**i for i in range(len(values))], k=1)[0]

    @staticmethod
    def _poisson(lam,k):
        return math.exp(-lam)*(lam**k)/math.factorial(k)

    @classmethod
    def _poisson_grid(cls, lh, la, max_goals=12):
        g={(h,a):cls._poisson(lh,h)*cls._poisson(la,a) for h in range(max_goals+1) for a in range(max_goals+1)}
        z=sum(g.values()) or 1.0
        return {k:v/z for k,v in g.items()}

    @staticmethod
    def _markets(grid):
        home=sum(p for (h,a),p in grid.items() if h>a); draw=sum(p for (h,a),p in grid.items() if h==a); away=sum(p for (h,a),p in grid.items() if h<a)
        btts=sum(p for (h,a),p in grid.items() if h>0 and a>0)
        totals={}
        for line in (0.5,1.5,2.5,3.5,4.5,5.5):
            totals[f"OVER {line}"]=sum(p for (h,a),p in grid.items() if h+a>line)
            totals[f"UNDER {line}"]=sum(p for (h,a),p in grid.items() if h+a<line)
        return {"1X2":{"1":home,"X":draw,"2":away},"DOUBLE_CHANCE":{"1X":home+draw,"X2":draw+away,"12":home+away},"DNB":{"1":home/(1-draw),"2":away/(1-draw)} if draw<1 else {},"BTTS":{"YES":btts,"NO":1-btts},"TOTAL_GOALS":totals,"CORRECT_SCORE":{f"{h}-{a}":p for (h,a),p in sorted(grid.items(),key=lambda kv:kv[1],reverse=True)[:15]}}

    def run(self,event,evidence):
        home=event.get("homeTeam") or {}; away=event.get("awayTeam") or {}; histories=evidence.get("history") or {}
        hr=self._team_samples(home.get("id"),(histories.get("home") or {}).get("events",[]),"home")
        ar=self._team_samples(away.get("id"),(histories.get("away") or {}).get("events",[]),"away")
        if not hr or not ar:
            return {"available":False,"version":self.VERSION,"reason":"insufficient_venue_specific_score_history","samples":{"home_venue":len(hr),"away_venue":len(ar)},"generated_at":time.time()}
        hg=[x[0] for x in hr]; hc=[x[1] for x in hr]; ag=[x[0] for x in ar]; ac=[x[1] for x in ar]
        rng=random.Random(f"{self.seed}:{event.get('id','')}")
        counts=Counter()
        for _ in range(self.simulations):
            h=int(round((self._weighted_choice(rng,hg)+self._weighted_choice(rng,ac))/2.0))
            a=int(round((self._weighted_choice(rng,ag)+self._weighted_choice(rng,hc))/2.0))
            counts[(max(0,h),max(0,a))]+=1
        empirical={k:v/sum(counts.values()) for k,v in counts.items()}
        hm=sum(hg)/len(hg); am=sum(ag)/len(ag); hd=sum(hc)/len(hc); ad=sum(ac)/len(ac)
        lh=max(.15,min(4.5,(hm+ad)/2)); la=max(.15,min(4.5,(am+hd)/2))
        poisson=self._poisson_grid(lh,la)
        n=min(len(hr),len(ar)); w=min(.70,.25+.045*n)
        hybrid={k:w*empirical.get(k,0)+(1-w)*poisson.get(k,0) for k in set(empirical)|set(poisson)}
        z=sum(hybrid.values()) or 1.0; hybrid={k:v/z for k,v in hybrid.items()}
        return {"available":True,"version":self.VERSION,"simulations":self.simulations,"samples":{"home_venue":len(hr),"away_venue":len(ar),"minimum":n},"observed_means":{"home_goals":hm,"home_conceded":hd,"away_goals":am,"away_conceded":ad},"expected_goals":{"home":lh,"away":la,"total":lh+la},"empirical_weight":w,"empirical_markets":self._markets(empirical),"poisson_markets":self._markets(poisson),"hybrid_markets":self._markets(hybrid),"stability":{"method":"empirical-resampling + Poisson smoothing","h2h_weight":0.0},"generated_at":time.time()}
