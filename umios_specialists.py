import math, re, time
from collections import defaultdict

class UMIOSSpecialistEnsemble:
    """Specialist evidence layer. Produces bounded feature adjustments; never overrides source truth."""
    FINISHED={"post","final","finished","completed","ended","after_penalties","after_extra_time"}
    def __init__(self):
        self.version="UMIOS-SPECIALISTS-v1"

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    @staticmethod
    def _players(payload,side):
        root=(payload or {}).get(side) or (payload or {}).get(side+"Team") or {}
        if isinstance(root,dict):
            for key in ("players","lineup","formation"):
                if isinstance(root.get(key),list):return root[key]
        return []

    def lineup(self,evidence):
        l=evidence.get("lineups") or {}
        if l.get("error"):return {"signal":0.0,"confidence":0.0,"missing":True}
        signals=[]
        for side in ("home","away"):
            players=self._players(l,side)
            missing=0; available=0
            for p in players:
                if not isinstance(p,dict):continue
                if p.get("missing") or p.get("status") in {"out","injured","suspended"}:missing+=1
                if p.get("substitute") is False or p.get("starter") is True:available+=1
            signals.append((missing,available))
        if not signals:return {"signal":0.0,"confidence":0.2,"missing":False}
        hm,ha=signals[0]; am,aa=signals[1]
        # Positive means home availability advantage; bounded to avoid overfitting.
        signal=max(-0.15,min(0.15,(am-hm)*0.02))
        return {"signal":round(signal,4),"home_missing":hm,"away_missing":am,"home_available":ha,"away_available":aa,"confidence":0.7 if (ha+aa)>=14 else 0.4,"missing":False}

    def tactical(self,evidence):
        stats=evidence.get("statistics") or {}
        nums=defaultdict(list)
        def walk(x):
            if isinstance(x,dict):
                for k,v in x.items():
                    if isinstance(v,(int,float)):nums[str(k).lower()].append(float(v))
                    elif isinstance(v,(dict,list)):walk(v)
            elif isinstance(x,list):
                for v in x:walk(v)
        walk(stats)
        def avg(keys):
            vals=[]
            for k,v in nums.items():
                if any(x in k for x in keys):vals.extend(v)
            return sum(vals)/len(vals) if vals else None
        shots=avg(("shots","total shots")); on=avg(("shots on target","on target")); possession=avg(("possession",))
        # This is intentionally a weak signal until team-attributed stat schemas are richer.
        strength=0.0
        if shots is not None and shots>12:strength+=0.02
        if on is not None and on>5:strength+=0.02
        if possession is not None and possession>55:strength+=0.01
        return {"signal":round(max(-0.08,min(0.08,strength)),4),"shots_indicator":shots,"on_target_indicator":on,"possession_indicator":possession,"confidence":0.3 if stats else 0.0}

    def goals(self,evidence):
        history=evidence.get("history") or {}
        def extract(events,side):
            vals=[]
            for e in events or []:
                st=((e.get("status") or {}).get("type") or {})
                if str(st.get("state") or "").lower() not in self.FINISHED and st.get("completed") is not True: continue
                h=e.get("homeTeam") or {};a=e.get("awayTeam") or {}
                hs=self._num((e.get("homeScore") or {}).get("current",h.get("score")))
                aws=self._num((e.get("awayScore") or {}).get("current",a.get("score")))
                if hs is None or aws is None:continue
                vals.append((hs,aws))
            return vals
        h=extract((history.get("home") or {}).get("events",[]),"home"); a=extract((history.get("away") or {}).get("events",[]),"away")
        if not h or not a:return {"signal":0.0,"confidence":0.0}
        hf=sum(x[0] for x in h)/len(h); hc=sum(x[1] for x in h)/len(h); af=sum(x[1] for x in a)/len(a); ac=sum(x[0] for x in a)/len(a)
        return {"home_attack":round(hf,3),"home_concede":round(hc,3),"away_attack":round(af,3),"away_concede":round(ac,3),"expected_total_proxy":round((hf+ac+af+hc)/2,3),"signal":round(max(-0.1,min(0.1,(hf+ac-af-hc)*0.025)),4),"confidence":0.7 if min(len(h),len(a))>=8 else 0.45}

    def volatility(self,evidence):
        history=evidence.get("history") or {}
        vals=[]
        for side in ("home","away"):
            for e in (history.get(side) or {}).get("events",[]):
                st=((e.get("status") or {}).get("type") or {})
                if str(st.get("state") or "").lower() not in self.FINISHED and st.get("completed") is not True: continue
                h=e.get("homeScore") or {};a=e.get("awayScore") or {}
                hs=self._num(h.get("current")); aw=self._num(a.get("current"))
                if hs is not None and aw is not None:vals.append(hs+aw)
        if len(vals)<5:return {"index":None,"regime":"UNKNOWN","confidence":0.0}
        mean=sum(vals)/len(vals); var=sum((x-mean)**2 for x in vals)/len(vals); idx=math.sqrt(var)/(mean or 1)
        regime="HIGH" if idx>0.8 else "LOW" if idx<0.45 else "NORMAL"
        return {"index":round(idx,4),"regime":regime,"confidence":min(1.0,len(vals)/20)}

    def markets(self,evidence):
        # Evidence availability map for specialist market engines.
        return {"goals":bool(evidence.get("history")),"corners":bool(evidence.get("statistics")),"cards":bool(evidence.get("incidents")),"btts":bool(evidence.get("history"))}

    def evaluate(self,event,evidence,prediction):
        return {"version":self.version,"lineup":self.lineup(evidence),"tactical":self.tactical(evidence),"goals":self.goals(evidence),"volatility":self.volatility(evidence),"market_coverage":self.markets(evidence),"generated_at":time.time()}
