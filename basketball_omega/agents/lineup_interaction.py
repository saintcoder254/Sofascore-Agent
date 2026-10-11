"""Sparse-aware lineup interaction model.

Uses pairwise synergy observations with shrinkage toward zero. This is a
transparent graph-like interaction layer, not a black-box claim of GAT training.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class LineupInteraction:
    team_id: str
    players: tuple[str,...]
    synergy: float
    uncertainty: float
    sample_possessions: float

class LineupInteractionAgent:
    name="basketball-lineup-interaction"

    def estimate(self, team_id, players, pair_history, expected_minutes=None):
        ids=tuple(str(x) for x in players)
        if len(ids)!=5: raise ValueError("lineup interaction requires exactly five players")
        total=0.0; variance=0.0; possessions=0.0
        for i in range(5):
            for j in range(i+1,5):
                key=tuple(sorted((ids[i],ids[j])))
                row=pair_history.get(key,{})
                n=max(0.0,float(row.get("possessions",0)))
                obs=float(row.get("net_rating",0.0))
                shrink=n/(n+100.0)
                total += obs*shrink
                variance += (max(0.5,float(row.get("std",5.0)))**2)*(1.0-shrink)
                possessions += n
        synergy=total/10.0
        uncertainty=math.sqrt(max(0.0,variance))/10.0
        return LineupInteraction(str(team_id),ids,synergy,uncertainty,possessions)
