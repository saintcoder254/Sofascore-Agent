"""Basketball player-state estimation with a Kalman-style Bayesian update.

State is an impact estimate and variance. The filter is deliberately simple,
transparent, and suitable as a prior until a trained RAPM/EPM source is wired.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class PlayerState:
    player_id: str
    impact: float
    variance: float
    observations: int
    last_update: float | None = None

class PlayerStateAgent:
    name="basketball-player-state"

    def __init__(self, prior_variance=9.0, observation_variance=16.0, decay=0.985):
        self.prior_variance=float(prior_variance)
        self.observation_variance=float(observation_variance)
        self.decay=float(decay)

    def update(self, prior: PlayerState | None, observation: float, sample_size=1, timestamp=None):
        if not math.isfinite(observation): raise ValueError("observation must be finite")
        if sample_size < 1: raise ValueError("sample_size must be >= 1")
        if prior is None:
            prior=PlayerState("",0.0,self.prior_variance,0,timestamp)
        p=max(1e-6,prior.variance / (self.decay if prior.observations else 1.0))
        r=max(1e-6,self.observation_variance/max(1,sample_size))
        gain=p/(p+r)
        impact=prior.impact+gain*(observation-prior.impact)
        variance=(1-gain)*p
        return PlayerState(prior.player_id,impact,variance,prior.observations+sample_size,timestamp)

    def from_history(self, player_id, observations):
        state=PlayerState(player_id,0.0,self.prior_variance,0,None)
        for row in observations:
            state=self.update(state,float(row["impact"]),int(row.get("sample_size",1)),row.get("timestamp"))
        return state
