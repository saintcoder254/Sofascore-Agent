"""Opponent/teammate-adjusted player impact estimation.

Transparent ridge-style iterative adjustment over player observations. The
model only consumes observations available before the prediction cutoff.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class AdjustedPlayerImpact:
    player_id: str
    adjusted_impact: float
    uncertainty: float
    observations: int
    opponent_adjustment: float
    teammate_adjustment: float

class OpponentTeammateAdjustmentAgent:
    name = "opponent-teammate-adjustment"

    def __init__(self, shrinkage: float = 20.0, iterations: int = 4):
        self.shrinkage = max(1.0, float(shrinkage))
        self.iterations = max(1, int(iterations))

    def fit(self, observations):
        rows = [dict(x) for x in observations]
        player = {}
        opp = {}
        team = {}
        for r in rows:
            pid = str(r["player_id"])
            oid = str(r.get("opponent_id", ""))
            tid = str(r.get("team_id", ""))
            player.setdefault(pid, []).append(r)
            opp.setdefault(oid, []).append(r)
            team.setdefault(tid, []).append(r)
        pmean = {k: sum(float(x["impact"]) for x in v) / len(v) for k,v in player.items()}
        omean = {k: sum(float(x["impact"]) for x in v) / len(v) for k,v in opp.items() if k}
        tmean = {k: sum(float(x["impact"]) for x in v) / len(v) for k,v in team.items() if k}
        grand = sum(float(r["impact"]) for r in rows) / len(rows) if rows else 0.0
        for _ in range(self.iterations):
            for pid, rs in player.items():
                vals=[]
                for r in rs:
                    oid=str(r.get("opponent_id","")); tid=str(r.get("team_id",""))
                    vals.append(float(r["impact"]) - (omean.get(oid,grand)-grand) - (tmean.get(tid,grand)-grand))
                raw=sum(vals)/len(vals)
                n=len(rs)
                pmean[pid]=(n*raw)/(n+self.shrinkage)  # ridge prior is neutral impact (0), not the sample grand mean
            for oid, rs in opp.items():
                if not oid: continue
                residual=[float(r["impact"])-pmean.get(str(r["player_id"]),grand) for r in rs]
                omean[oid]=sum(residual)/len(residual)+grand
        out={}
        for pid, rs in player.items():
            n=len(rs)
            adj=pmean[pid]
            var=sum((float(r["impact"])-adj)**2 for r in rs)/max(1,n-1)
            uncertainty=math.sqrt(max(0.01,var)/max(1,n)) + self.shrinkage/(n+self.shrinkage)
            opponent_adj=sum(omean.get(str(r.get("opponent_id","")),grand)-grand for r in rs)/n
            teammate_adj=sum(tmean.get(str(r.get("team_id","")),grand)-grand for r in rs)/n
            out[pid]=AdjustedPlayerImpact(pid,adj,uncertainty,n,opponent_adj,teammate_adj)
        return out
