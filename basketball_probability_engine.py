"""UMIOS TITAN basketball probability engine.

Basketball-specific replacement for the football/Poisson goal model.
It models points as a correlated continuous distribution, uses recent
score evidence, optional possession/stat evidence, empirical variance,
scenario shocks and a deterministic Monte Carlo layer.

It never manufactures a probability when the evidence is insufficient.
"""
from __future__ import annotations
import math, random, re, statistics, time
from typing import Any, Dict, List, Optional

class BasketballProbabilityEngine:
    VERSION="UMIOS-BASKETBALL-FUSION-v2.0"
    FINISHED={"post","final","finished","completed","ended","after_penalties","after_extra_time"}

    def __init__(self, simulations=10000):
        self.simulations=max(5000,int(simulations))

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    @classmethod
    def _finished(cls,e):
        st=((e.get("status") or {}).get("type") or {}) if isinstance(e,dict) else {}
        return str(st.get("state") or "").lower() in cls.FINISHED or st.get("completed") is True

    @classmethod
    def _sport(cls,event,evidence):
        vals=[event.get(k) for k in ("sport","sportName","sportSlug","eventType","category","tournamentName")]
        vals += [evidence.get(k) for k in ("sport","sportName","sportSlug","category")]
        s=" ".join(str(x or "") for x in vals).lower()
        return "basketball" if ("basket" in s or "nba" in s or "wnba" in s) else "other"

    @classmethod
    def _games(cls,evidence,side):
        rows=[]
        for e in ((evidence.get("history") or {}).get(side) or {}).get("events",[]) or []:
            if not isinstance(e,dict) or not cls._finished(e):continue
            h=e.get("homeTeam") or {}; a=e.get("awayTeam") or {}
            hs=cls._num((e.get("homeScore") or {}).get("current",h.get("score")))
            aw=cls._num((e.get("awayScore") or {}).get("current",a.get("score")))
            if hs is None or aw is None:continue
            rows.append({"home_id":h.get("id"),"away_id":a.get("id"),"home":hs,"away":aw,"total":hs+aw})
        return rows

    @staticmethod
    def _team_points(games,team_id):
        scored=[]; conceded=[]; totals=[]
        for g in games:
            if str(g["home_id"])==str(team_id):
                scored.append(g["home"]);conceded.append(g["away"])
            elif str(g["away_id"])==str(team_id):
                scored.append(g["away"]);conceded.append(g["home"])
            totals.append(g["total"])
        return scored,conceded,totals

    @classmethod
    def _recent_stats(cls,evidence,team_id):
        games=(evidence.get("history") or {}).get("home",{}).get("events",[])+ (evidence.get("history") or {}).get("away",{}).get("events",[])
        games=[g for g in games if isinstance(g,dict) and cls._finished(g)]
        scored=[];conceded=[]
        for e in games:
            h=e.get("homeTeam") or {};a=e.get("awayTeam") or {}
            hs=cls._num((e.get("homeScore") or {}).get("current"));aw=cls._num((e.get("awayScore") or {}).get("current"))
            if hs is None or aw is None:continue
            if str(h.get("id"))==str(team_id):scored.append(hs);conceded.append(aw)
            elif str(a.get("id"))==str(team_id):scored.append(aw);conceded.append(hs)
        return scored[-10:],conceded[-10:]

    @staticmethod
    def _mean(xs): return statistics.mean(xs) if xs else None
    @staticmethod
    def _sd(xs,default=12.0):
        if len(xs)>=2:return max(7.0,statistics.stdev(xs))
        return default

    @staticmethod
    def _market_and_line(selection):
        s=str(selection or "").upper().strip()
        m=re.search(r"(OVER|UNDER|O|U)\s*([0-9]+(?:\.[05])?)",s)
        if m:return ("OVER" if m.group(1) in {"OVER","O"} else "UNDER",float(m.group(2)))
        return None,None

    @classmethod
    def _extract_stat_values(cls,evidence,keys):
        vals=[]
        def walk(x):
            if isinstance(x,dict):
                for k,v in x.items():
                    if isinstance(v,(int,float)) and any(key in str(k).lower() for key in keys):vals.append(float(v))
                    elif isinstance(v,(dict,list)):walk(v)
            elif isinstance(x,list):
                for v in x:walk(v)
        walk(evidence.get("statistics") or {})
        return vals

    @staticmethod
    def _normal_cdf(x,mu,sd):
        return 0.5*(1+math.erf((x-mu)/(max(sd,1e-9)*math.sqrt(2))))

    def _estimate(self,event,evidence):
        home=event.get("homeTeam") or {};away=event.get("awayTeam") or {}
        hs,hc=self._recent_stats(evidence,home.get("id"));as_,ac=self._recent_stats(evidence,away.get("id"))
        if min(len(hs),len(as_))<5:return None
        home_attack=self._mean(hs); home_def=self._mean(hc); away_attack=self._mean(as_); away_def=self._mean(ac)
        # Matchup expectation: offense is blended with opponent concession rate.
        hp=0.58*home_attack+0.42*away_def+2.0
        ap=0.58*away_attack+0.42*home_def
        # Optional pace proxies are used only as bounded multipliers.
        pace=self._extract_stat_values(evidence,("pace","possessions","possessions per game"))
        if pace:
            league_pace=self._mean(pace)
            if league_pace and league_pace>0:
                factor=max(0.92,min(1.08,league_pace/100.0))
                hp*=factor;ap*=factor
        totals=hs+hc+as_+ac
        empirical=[x+y for x,y in zip(hs[-5:],as_[-5:])]
        sd=max(self._sd(empirical,12.0),self._sd(totals,13.0)*0.70)
        # Shared pace/scoring shock creates positive correlation between team scores.
        rho=0.18
        return {"home_points":max(55.0,min(140.0,hp)),"away_points":max(55.0,min(140.0,ap)),
                "expected_total":max(100.0,min(280.0,hp+ap)),"sd_total":max(9.0,min(28.0,sd)),
                "rho":rho,"home_samples":len(hs),"away_samples":len(as_),
                "recent_totals":empirical[-5:],"team_scored":{"home":hs,"away":as_},
                "team_conceded":{"home":hc,"away":ac}}

    @classmethod
    def _mc(cls,mu_h,mu_a,sd_total,rho,n,seed):
        rng=random.Random(seed); rows=[]; under_count={}
        # Derive team SD from total SD and impose a shared latent pace factor.
        sd_h=max(7.0,sd_total*0.52);sd_a=max(7.0,sd_total*0.52)
        shared=max(0.0,min(sd_h,sd_a))*rho
        for _ in range(n):
            z=rng.gauss(0,1);e1=rng.gauss(0,1);e2=rng.gauss(0,1)
            h=max(0.0,mu_h+shared*z+math.sqrt(max(0.0,sd_h*sd_h-shared*shared))*e1)
            a=max(0.0,mu_a+shared*z+math.sqrt(max(0.0,sd_a*sd_a-shared*shared))*e2)
            rows.append((h,a,h+a))
        return rows

    def run(self,event,evidence,gate,simulations=None):
        if gate.get("state")!="QUALIFIED":return {"state":"NO_BET","reason":"qualification_gate_blocked","candidates":[]}
        if self._sport(event,evidence)!="basketball":
            return {"state":"NOT_APPLICABLE","model":self.VERSION}
        est=self._estimate(event,evidence)
        if not est:return {"state":"NO_BET","reason":"basketball_history_insufficient","candidates":[],"model":self.VERSION}
        n=max(self.simulations,int(simulations or self.simulations))
        rows=self._mc(est["home_points"],est["away_points"],est["sd_total"],est["rho"],n,seed=f"{event.get('id')}:{est['expected_total']:.4f}")
        totals=[r[2] for r in rows]
        observed=[]
        odds=evidence.get("odds") or {}
        for payload in odds.values():
            if not isinstance(payload,dict):continue
            for market in payload.get("markets",[]) or []:
                name=str(market.get("name") or market.get("marketName") or "").lower()
                if not any(k in name for k in ("total","over/under","over under","points")):continue
                for c in market.get("choices",[]) or []:
                    odd=self._num(c.get("decimalValue",c.get("odds")))
                    if odd is None or odd<=1:continue
                    direction,line=self._market_and_line(c.get("name") or c.get("label"))
                    if direction and line is not None:observed.append((direction,line,odd))
        # De-vig total choices by line; compare model probabilities only at matching lines.
        candidates=[]
        for direction,line,odd in observed:
            same=[x for x in observed if x[1]==line]
            z=sum(1/x[2] for x in same)
            market_p=(1/odd)/z if z else None
            if market_p is None:continue
            if direction=="OVER":p=sum(t>line for t in totals)/n
            else:p=sum(t<line for t in totals)/n
            edge=p-market_p;ev=p*odd-1
            # Model uncertainty widens with sample scarcity and empirical variance.
            sample=min(est["home_samples"],est["away_samples"])
            confidence=min(1.0,0.45+sample/20.0)
            required_edge=0.055+(1-confidence)*0.06
            status="QUALIFIED" if p>=0.55 and edge>=required_edge and ev>=0.05 else "REJECTED"
            candidates.append({"market":"TOTAL_POINTS","selection":f"{direction} {line:g}","odds":odd,"line":line,
                               "model_probability":round(p,4),"market_probability":round(market_p,4),"edge":round(edge,4),
                               "expected_value":round(ev,4),"status":status,"confidence":round(confidence,4)})
        qualified=sorted((x for x in candidates if x["status"]=="QUALIFIED"),key=lambda x:(x["edge"],x["expected_value"]),reverse=True)
        sel=qualified[0] if qualified else None
        if sel:
            sel["tail_risk"]=round(sum(t>sel["line"] for t in totals)/n,4)
        return {"state":"QUALIFIED_PREDICTION" if sel else "NO_BET","model":self.VERSION,
                "simulations":n,"expected_points":{"home":round(est["home_points"],2),"away":round(est["away_points"],2)},
                "expected_total":round(est["expected_total"],2),"distribution_sd":round(est["sd_total"],2),
                "history":{"home_games":est["home_samples"],"away_games":est["away_samples"],"minimum_games":min(est["home_samples"],est["away_samples"])},
                "simulated_totals":totals if sel else totals[:2000],"candidates":candidates,"selection":sel,
                "generated_at":time.time()}