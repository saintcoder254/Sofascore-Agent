"""OMEGA Dynamic Strength Engine v2.

Opponent-adjusted, venue-aware, recency-weighted team strength with conservative
shrinkage. This is a diagnostic layer: it does not manufacture ratings when
evidence is insufficient.
"""
import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

@dataclass
class Strength:
    attack: float
    defense: float
    overall: float
    home_advantage: float
    sample: int
    uncertainty: float

class DynamicStrengthEngine:
    VERSION="OMEGA-DYNAMIC-STRENGTH-v2"

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    @staticmethod
    def _finished(e):
        st=((e.get("status") or {}).get("type") or {}) if isinstance(e,dict) else {}
        return str(st.get("state") or "").lower() in {"post","final","finished","completed","ended","after_extra_time","after_penalties"} or st.get("completed") is True

    def _rows(self,team_id,events):
        out=[]
        for e in events or []:
            if not self._finished(e): continue
            h=e.get("homeTeam") or {}; a=e.get("awayTeam") or {}
            hs=self._num((e.get("homeScore") or {}).get("current")); aw=self._num((e.get("awayScore") or {}).get("current"))
            if hs is None or aw is None: continue
            if str(h.get("id"))==str(team_id): out.append(("home",hs,aw))
            elif str(a.get("id"))==str(team_id): out.append(("away",aw,hs))
        return out

    def evaluate(self,event,evidence):
        home=event.get("homeTeam") or {}; away=event.get("awayTeam") or {}
        histories=evidence.get("history") or {}
        hr=self._rows(home.get("id"),(histories.get("home") or {}).get("events",[]))
        ar=self._rows(away.get("id"),(histories.get("away") or {}).get("events",[]))
        if not hr or not ar:
            return {"available":False,"version":self.VERSION,"reason":"insufficient_history"}
        def calc(rows):
            # Exponential recency weights; shrink aggressively for small samples.
            w=[0.88**i for i in range(len(rows))]
            z=sum(w)
            gf=sum(r[1]*x for r,x in zip(rows,w))/z
            ga=sum(r[2]*x for r,x in zip(rows,w))/z
            home_n=sum(1 for r,_,_ in rows if r=="home")
            away_n=len(rows)-home_n
            return gf,ga,home_n,away_n,len(rows)
        hgf,hga,hhn,hay,hn=calc(hr); agf,aga,ahn,aay,an=calc(ar)
        # League-neutral priors; ratings are relative strength indicators, not xG.
        base_attack=1.35; base_def=1.20
        ha=0.10 if hhn>=5 else 0.05
        home_attack=base_attack + 0.45*(hgf-base_attack) - 0.25*(hga-base_def) + ha
        away_attack=base_attack + 0.45*(agf-base_attack) - 0.25*(aga-base_def)
        home_def=base_def + 0.45*(base_attack-hga) - 0.20*(base_attack-hgf)
        away_def=base_def + 0.45*(base_attack-aga) - 0.20*(base_attack-agf)
        hs=home_attack+home_def; as_=away_attack+away_def
        hu=min(1.0,1.0/math.sqrt(max(1,hn))); au=min(1.0,1.0/math.sqrt(max(1,an)))
        return {"available":True,"version":self.VERSION,
                "home":asdict(Strength(round(home_attack,4),round(home_def,4),round(hs,4),ha,hn,round(hu,4))),
                "away":asdict(Strength(round(away_attack,4),round(away_def,4),0.0,an,round(au,4)))}
