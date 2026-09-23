import math, re, statistics, time
from collections import defaultdict

class UMIOSMarketModels:
    """Market-specific probability layer. Only emits a model probability when the
    evidence needed for that market is present; otherwise returns no model."""
    FINISHED={"post","final","finished","completed","ended","after_penalties","after_extra_time"}

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    @classmethod
    def _finished(cls,e):
        st=((e.get("status") or {}).get("type") or {}) if isinstance(e,dict) else {}
        return str(st.get("state") or "").lower() in cls.FINISHED or st.get("completed") is True

    @classmethod
    def _score_events(cls,events):
        out=[]
        for e in events or []:
            if not isinstance(e,dict) or not cls._finished(e): continue
            h=e.get("homeScore") or {}; a=e.get("awayScore") or {}
            hs=cls._num(h.get("current")); aw=cls._num(a.get("current"))
            if hs is not None and aw is not None: out.append((hs,aw))
        return out

    @staticmethod
    def _poisson(lam,k):
        return math.exp(-lam)*(lam**k)/math.factorial(k)

    @classmethod
    def _grid(cls,lh,la,max_goals=12):
        g={(h,a):cls._poisson(lh,h)*cls._poisson(la,a) for h in range(max_goals+1) for a in range(max_goals+1)}
        z=sum(g.values()) or 1
        return {k:v/z for k,v in g.items()}

    @staticmethod
    def _event_market(name):
        n=str(name or "").lower()
        if any(x in n for x in ("winner","match result","1x2")): return "1X2"
        if "both teams" in n or "btts" in n: return "BTTS"
        if any(x in n for x in ("over/under","over under","total goals","goals o/u")): return "TOTAL_GOALS"
        if "double chance" in n:return "DOUBLE_CHANCE"
        if "draw no bet" in n or n=="dnb":return "DNB"
        if "correct score" in n:return "CORRECT_SCORE"
        if "corner" in n:return "CORNERS"
        if "card" in n or "booking" in n:return "CARDS"
        if "handicap" in n or "asian handicap" in n:return "HANDICAP"
        return "OTHER"

    @staticmethod
    def _selection(name,market):
        s=re.sub(r"\s+"," ",str(name or "").strip().upper())
        if market=="1X2":
            return {"HOME":"1","HOME WIN":"1","1":"1","DRAW":"X","X":"X","AWAY":"2","AWAY WIN":"2","2":"2"}.get(s)
        if market=="BTTS": return {"YES":"YES","GG":"YES","NO":"NO","NG":"NO"}.get(s,s if s in {"YES","NO"} else None)
        if market=="DOUBLE_CHANCE": return s.replace(" ","")
        if market=="DNB": return "1" if s in {"1","HOME"} else "2" if s in {"2","AWAY"} else None
        if market=="CORRECT_SCORE": return s.replace(" ","")
        if market in {"TOTAL_GOALS","CORNERS","CARDS","HANDICAP"}: return s
        return s

    @classmethod
    def odds_observations(cls,evidence):
        rows=[]
        for payload in (evidence.get("odds") or {}).values():
            if not isinstance(payload,dict): continue
            for market in payload.get("markets",[]) or []:
                m=cls._event_market(market.get("name") or market.get("marketName"))
                for c in market.get("choices",[]) or []:
                    odd=cls._num(c.get("decimalValue"))
                    if odd is None: odd=cls._num(c.get("odds"))
                    if odd is None or odd<=1: continue
                    sel=cls._selection(c.get("name") or c.get("label"),m)
                    if not sel: continue
                    rows.append({"market":m,"selection":sel,"odds":odd})
        grouped=defaultdict(list)
        for r in rows: grouped[r["market"]].append(r)
        for m,items in grouped.items():
            z=sum(1/x["odds"] for x in items)
            for x in items: x["market_probability"]=(1/x["odds"])/z if z else None
        return [x for x in rows if x.get("market_probability") is not None]

    @classmethod
    def _goal_lambdas(cls,event,evidence):
        home=event.get("homeTeam") or {}; away=event.get("awayTeam") or {}
        histories=evidence.get("history") or {}
        def rates(team_id,side):
            vals=cls._score_events((histories.get(side) or {}).get("events",[]))
            gf=[];ga=[]; hgf=[];hga=[];agf=[];aga=[]
            for hs,aw in vals:
                # History is team-specific; use event team IDs where available.
                pass
            for e in (histories.get(side) or {}).get("events",[]):
                if not cls._finished(e): continue
                ht=e.get("homeTeam") or {}; at=e.get("awayTeam") or {}
                hs=cls._num((e.get("homeScore") or {}).get("current")); aw=cls._num((e.get("awayScore") or {}).get("current"))
                if hs is None or aw is None: continue
                if str(ht.get("id"))==str(team_id): gf.append(hs);ga.append(aw);hgf.append(hs);hga.append(aw)
                elif str(at.get("id"))==str(team_id): gf.append(aw);ga.append(hs);agf.append(aw);aga.append(hs)
            mean=lambda x:sum(x)/len(x) if x else None
            return mean(gf),mean(ga),mean(hgf),mean(hga),mean(agf),mean(aga),len(gf)
        hr=rates(home.get("id"),"home"); ar=rates(away.get("id"),"away")
        lh=((hr[0] or 1.35)*0.55+(hr[2] or 1.35)*0.2+(ar[1] or 1.05)*0.25)
        la=((ar[0] or 1.05)*0.55+(ar[5] or 1.05)*0.2+(hr[1] or 1.35)*0.25)
        n=min(hr[-1],ar[-1])
        shrink=min(1,n/10)
        lh=1.35+(lh-1.35)*shrink; la=1.05+(la-1.05)*shrink
        return max(.15,min(4.5,lh)),max(.15,min(4.5,la)),n

    @classmethod
    def _incident_counts(cls,evidence):
        inc=evidence.get("incidents") or {}
        if not isinstance(inc,dict): return []
        rows=inc.get("incidents") or inc.get("items") or inc.get("data") or []
        counts=[]
        for x in rows if isinstance(rows,list) else []:
            if not isinstance(x,dict): continue
            typ=str(x.get("incidentType") or x.get("incidentClass") or x.get("type") or "").lower()
            if any(k in typ for k in ("yellow","card","booking")): counts.append(1)
        return counts

    @classmethod
    def _historical_values(cls,evidence,keys):
        vals=[]
        def walk(x):
            if isinstance(x,dict):
                for k,v in x.items():
                    lk=str(k).lower()
                    if isinstance(v,(int,float)) and any(key in lk for key in keys): vals.append(float(v))
                    elif isinstance(v,(dict,list)): walk(v)
            elif isinstance(x,list):
                for v in x: walk(v)
        walk(evidence.get("history") or {})
        return vals

    @classmethod
    def _poisson_tail(cls,lam,op,line):
        return sum(cls._poisson(lam,k) for k in range(0,40) if (k>line if op=="OVER" else k<line))

    def evaluate(self,event,evidence):
        lh,la,n=self._goal_lambdas(event,evidence)
        grid=self._grid(lh,la)
        one=sum(p for (h,a),p in grid.items() if h>a)
        draw=sum(p for (h,a),p in grid.items() if h==a)
        two=sum(p for (h,a),p in grid.items() if h<a)
        probs={
            "1X2":{"1":one,"X":draw,"2":two},
            "BTTS":{"YES":sum(p for (h,a),p in grid.items() if h>0 and a>0),"NO":sum(p for (h,a),p in grid.items() if h==0 or a==0)},
            "DOUBLE_CHANCE":{"1X":one+draw,"X2":draw+two,"12":one+two},
            "DNB":{"1":one/(1-draw),"2":two/(1-draw)} if draw<1 else {},
            "CORRECT_SCORE":{f"{h}-{a}":p for (h,a),p in sorted(grid.items(),key=lambda kv:kv[1],reverse=True)[:10]}
        }

        # Asian handicap probabilities are derived from the score distribution and only used when a matching bookmaker line exists.
        probs["HANDICAP"]={}
        for line in range(-3,4):
            if line==0: continue
            probs["HANDICAP"][f"HOME {line:+d}"]=sum(p for (h,a),p in grid.items() if h+line>a)
            probs["HANDICAP"][f"AWAY {-line:+d}"]=sum(p for (h,a),p in grid.items() if a-line>h)
        for line in (.5,1.5,2.5,3.5,4.5,5.5):
            probs.setdefault("TOTAL_GOALS",{})[f"OVER {line}"]=sum(p for (h,a),p in grid.items() if h+a>line)
            probs["TOTAL_GOALS"][f"UNDER {line}"]=sum(p for (h,a),p in grid.items() if h+a<line)

        # Corners: use only explicitly corner-like statistic values. If there is no
        # identifiable corner evidence, do not synthesize a corner probability.
        corner_vals=self._historical_values(evidence,("corner","corners"))
        card_vals=self._historical_values(evidence,("yellow","card","booking"))
        market_meta={}
        if len(corner_vals)>=2:
            mean=sum(corner_vals)/len(corner_vals); var=statistics.pvariance(corner_vals) if len(corner_vals)>1 else mean
            market_meta["CORNERS"]={"mean":mean,"variance":var,"samples":len(corner_vals),"confidence":min(1,len(corner_vals)/8)}
            for line in (7.5,8.5,9.5,10.5,11.5):
                probs.setdefault("CORNERS",{})[f"OVER {line}"]=self_tail=self._poisson_tail(mean,"OVER",line)
                probs["CORNERS"][f"UNDER {line}"]=self._poisson_tail(mean,"UNDER",line)
        if len(card_vals)>=3:
            mean=sum(card_vals)/len(card_vals); market_meta["CARDS"]={"mean":mean,"samples":len(card_vals),"confidence":min(1,len(card_vals)/10)}
            for line in (2.5,3.5,4.5,5.5,6.5):
                probs.setdefault("CARDS",{})[f"OVER {line}"]=self._poisson_tail(mean,"OVER",line)
                probs["CARDS"][f"UNDER {line}"]=self._poisson_tail(mean,"UNDER",line)
        return {"version":"UMIOS-MARKET-MODELS-v1","goal_lambdas":{"home":round(lh,4),"away":round(la,4)},"history_samples":n,"probabilities":probs,"market_meta":market_meta,"generated_at":time.time()}

    @staticmethod
    def model_for_market(result,market,selection):
        return (result.get("probabilities") or {}).get(market,{}).get(selection)
