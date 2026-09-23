import math, random, re, time
from collections import defaultdict
from umios_market_models import UMIOSMarketModels

class UMIOSProbabilityEngine:
    """Conservative probability engine with market-specific models, Monte Carlo, form, and value gates."""
    def __init__(self):
        self.market_models=UMIOSMarketModels()
    MARKETS=("1X2","BTTS","TOTAL_GOALS","DOUBLE_CHANCE","DNB","CORRECT_SCORE","CORNERS","CARDS","HANDICAP")
    FINISHED={"post","final","finished","completed"}

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    @classmethod
    def _finished(cls,e):
        st=((e.get("status") or {}).get("type") or {}) if isinstance(e,dict) else {}
        state=str(st.get("state") or "").lower()
        if state in cls.FINISHED or st.get("completed") is True:return True
        # Historical SofaScore endpoints occasionally expose a score without a completed flag.
        return state in {"ended","after_penalties","after_extra_time"}

    @classmethod
    def _events(cls,history):
        out=[]
        for e in history or []:
            if not isinstance(e,dict) or e.get("error") or not cls._finished(e):continue
            out.append(e)
        return out

    @classmethod
    def _team_rates(cls,team_id,events):
        gf=[];ga=[];home_gf=[];home_ga=[];away_gf=[];away_ga=[]
        for e in cls._events(events):
            h=e.get("homeTeam") or {}; a=e.get("awayTeam") or {}
            if str(h.get("id"))==str(team_id): venue="home"
            elif str(a.get("id"))==str(team_id): venue="away"
            else: continue
            hs=cls._num((e.get("homeScore") or {}).get("current"))
            aas=cls._num((e.get("awayScore") or {}).get("current"))
            if hs is None: hs=cls._num(h.get("score"))
            if aas is None: aas=cls._num(a.get("score"))
            if hs is None or aas is None:continue
            scored=hs if venue=="home" else aas; conceded=aas if venue=="home" else hs
            gf.append(scored);ga.append(conceded)
            if venue=="home":home_gf.append(scored);home_ga.append(conceded)
            else:away_gf.append(scored);away_ga.append(conceded)
        mean=lambda x: sum(x)/len(x) if x else None
        return {"games":len(gf),"gf":mean(gf),"ga":mean(ga),"home_gf":mean(home_gf),"home_ga":mean(home_ga),"away_gf":mean(away_gf),"away_ga":mean(away_ga),
                "gf_last5":mean(gf[:5]),"ga_last5":mean(ga[:5]),"gf_prev":mean(gf[5:10]),"ga_prev":mean(ga[5:10])}

    @staticmethod
    def _blend(*vals):
        vals=[x for x in vals if x is not None]
        return sum(vals)/len(vals) if vals else None

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
        while p>L:k+=1;p*=rng.random()
        return k-1

    @classmethod
    def _monte_carlo(cls,lh,la,n=10000,seed=None):
        n=max(1000,int(n))
        rng=random.Random(seed if seed is not None else int(time.time()*1000))
        counts=defaultdict(int)
        for _ in range(n):
            counts[(cls._sample_poisson(rng,lh),cls._sample_poisson(rng,la))]+=1
        return {k:v/n for k,v in counts.items()}

    @staticmethod
    def _market_probs(grid):
        out={"1X2":{},"BTTS":{},"TOTAL_GOALS":{},"DOUBLE_CHANCE":{},"DNB":{},"CORRECT_SCORE":{}}
        h1=sum(p for (h,a),p in grid.items() if h>a); dr=sum(p for (h,a),p in grid.items() if h==a); a2=sum(p for (h,a),p in grid.items() if h<a)
        out["1X2"]={"1":h1,"X":dr,"2":a2}
        out["BTTS"]={"YES":sum(p for (h,a),p in grid.items() if h>0 and a>0),"NO":sum(p for (h,a),p in grid.items() if h==0 or a==0)}
        out["DOUBLE_CHANCE"]={"1X":h1+dr,"X2":dr+a2,"12":h1+a2}
        denom=1-dr
        out["DNB"]={"1":h1/denom,"2":a2/denom} if denom>0 else {}
        for line in (0.5,1.5,2.5,3.5,4.5,5.5):
            out["TOTAL_GOALS"][f"OVER {line}"]=sum(p for (h,a),p in grid.items() if h+a>line)
            out["TOTAL_GOALS"][f"UNDER {line}"]=sum(p for (h,a),p in grid.items() if h+a<line)
        out["CORRECT_SCORE"]={f"{h}-{a}":p for (h,a),p in sorted(grid.items(),key=lambda x:x[1],reverse=True)[:10]}
        return out

    @staticmethod
    def _market_type(name):
        n=str(name or "").lower()
        if any(x in n for x in ("winner","match result","1x2")):return "1X2"
        if "both teams" in n or "btts" in n:return "BTTS"
        if any(x in n for x in ("over/under","over under","total goals","goals o/u")):return "TOTAL_GOALS"
        if "double chance" in n:return "DOUBLE_CHANCE"
        if "draw no bet" in n or n=="dnb":return "DNB"
        if "correct score" in n:return "CORRECT_SCORE"
        return "OTHER"

    @staticmethod
    def _selection(name,market):
        s=str(name or "").strip().upper()
        s=re.sub(r"\\s+"," ",s)
        if market=="1X2":
            if s in {"1","HOME","HOME WIN"}:return "1"
            if s in {"X","DRAW"}:return "X"
            if s in {"2","AWAY","AWAY WIN"}:return "2"
        if market=="BTTS":
            if s in {"YES","GG"}:return "YES"
            if s in {"NO","NG"}:return "NO"
        if market=="DOUBLE_CHANCE":
            return s.replace(" ","")
        if market=="DNB" and s in {"1","HOME","2","AWAY"}:return "1" if s in {"1","HOME"} else "2"
        if market=="CORRECT_SCORE":return s.replace(" ","")
        if market=="TOTAL_GOALS":
            m=re.search(r"(OVER|UNDER)\\s*(\\d+(?:\\.\\d+)?)",s)
            return f"{m.group(1)} {float(m.group(2))}" if m else s
        return s

    @classmethod
    def _observations(cls,evidence):
        rows=[]
        for payload in (evidence.get("odds") or {}).values():
            if not isinstance(payload,dict):continue
            for m in payload.get("markets",[]) or []:
                market=cls._market_type(m.get("name") or m.get("marketName"))
                choices=m.get("choices") or []
                for c in choices:
                    odd=cls._num(c.get("decimalValue"))
                    if odd is None:odd=cls._num(c.get("odds"))
                    if odd is None or odd<=1:continue
                    sel=cls._selection(c.get("name") or c.get("label"),market)
                    if not sel:continue
                    rows.append({"market":market,"selection":sel,"odds":odd})
        # De-vig within each bookmaker market so edge is against a fair market benchmark.
        grouped=defaultdict(list)
        for r in rows:
            grouped[r["market"]].append(r)
        for market,items in grouped.items():
            total=sum(1/x["odds"] for x in items)
            for x in items:
                x["market_probability"]=(1/x["odds"])/total if total>0 else None
        return [x for x in rows if x["market_probability"] is not None]

    @staticmethod
    def _trend(rate):
        if rate["gf_last5"] is None or rate["gf_prev"] is None:return 0.0
        return max(-0.35,min(0.35,(rate["gf_last5"]-rate["gf_prev"])*0.12))

    def run(self,event,evidence,gate,simulations=10000):
        if gate.get("state")!="QUALIFIED":return {"state":"NO_BET","reason":"qualification_gate_blocked","candidates":[]}
        home=event.get("homeTeam") or {}; away=event.get("awayTeam") or {}
        hh=self._team_rates(home.get("id"),(evidence.get("history",{}).get("home") or {}).get("events",[]))
        aa=self._team_rates(away.get("id"),(evidence.get("history",{}).get("away") or {}).get("events",[]))
        sample=min(hh["games"],aa["games"])
        # Venue-aware baseline with modest recency trend. Thin samples are shrunk to conservative priors.
        lh=self._blend(hh["gf"],aa["ga"],1.35)*0.55+self._blend(hh["home_gf"],aa["away_ga"],1.35)*0.45
        la=self._blend(aa["gf"],hh["ga"],1.05)*0.55+self._blend(aa["away_gf"],hh["home_ga"],1.05)*0.45
        lh*=1+self._trend(hh); la*=1+self._trend(aa)
        shrink=min(1.0,sample/10.0)
        lh=1.35+(lh-1.35)*shrink; la=1.05+(la-1.05)*shrink
        lh=max(0.15,min(4.5,lh)); la=max(0.15,min(4.5,la))
        grid=self._grid(lh,la); mc=self._monte_carlo(lh,la,simulations,seed=f"{event.get('id','')}:{round(lh,4)}:{round(la,4)}")
        gp=self._market_probs(grid); mp=self._market_probs(mc)
        ensemble={m:{k:round(0.65*v+0.35*mp.get(m,{}).get(k,v),6) for k,v in items.items()} for m,items in gp.items()}
        market_specific=self.market_models.evaluate(event,evidence)
        # Specialized models take precedence for the markets they can support.
        specialized=market_specific.get("probabilities") or {}
        ensemble={m:dict(v) for m,v in ensemble.items()}
        for market,vals in specialized.items():
            if vals: ensemble[market]=vals
        observed=self.market_models.odds_observations(evidence); candidates=[]
        history_gate=sample>=5
        for row in observed:
            market=row["market"]; sel=row["selection"]; p=ensemble.get(market,{}).get(sel)
            if p is None:continue
            edge=p-row["market_probability"]; ev=p*row["odds"]-1
            # Adversarial value gate: large unexplained edges are rejected rather than automatically trusted.
            suspicious=edge>0.20 or ev>0.35
            status="QUALIFIED" if history_gate and not suspicious and edge>=0.04 and ev>=0.05 and p>=0.55 else "REJECTED"
            candidates.append({"market":market,"selection":sel,"odds":row["odds"],"model_probability":round(p,4),"market_probability":round(row["market_probability"],4),"edge":round(edge,4),"expected_value":round(ev,4),"status":status,"suspicious_edge":suspicious})
        qualified=sorted((x for x in candidates if x["status"]=="QUALIFIED"),key=lambda x:(x["edge"],x["expected_value"]),reverse=True)
        return {"state":"QUALIFIED_PREDICTION" if qualified else "NO_BET","model":"UMIOS-MarketSpecific+Poisson+MonteCarlo+FormTrend","simulations":max(1000,int(simulations)),
                "expected_goals":{"home":round(lh,3),"away":round(la,3)},"history":{"home_games":hh["games"],"away_games":aa["games"],"minimum_games":sample},
                "form_trend":{"home":round(self._trend(hh),4),"away":round(self._trend(aa),4)},"probabilities":ensemble,"market_models":market_specific,
                "market_observations":len(observed),"candidates":candidates,"selection":qualified[0] if qualified else None,"generated_at":time.time()}
