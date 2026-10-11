import math
from dataclasses import dataclass, field

@dataclass
class OnlineWeightLearner:
    """Bounded recursive-error learner. It updates weights from realized errors,
    not from bookmaker outcomes alone, and keeps a conservative prior."""
    learning_rate: float=.03
    weights: dict=field(default_factory=lambda:{"player-impact":1.0,"minutes-projection":1.0,"lineup-synergy":1.0,"possession-efficiency":1.0,"matchup-interaction":1.0,"possession-monte-carlo":1.0})
    samples: int=0
    def update(self, opinions, actual_margin):
        self.samples+=1; losses={}
        for o in opinions:
            if o.fair_margin is None: continue
            err=float(actual_margin)-float(o.fair_margin); name=o.agent
            old=self.weights.get(name,1.0)
            # Huber-like bounded update prevents one outlier game from rewriting the model.
            grad=max(-8.0,min(8.0,err))*self.learning_rate
            self.weights[name]=max(.25,min(2.0,old+grad/8.0)); losses[name]=err
        return {"samples":self.samples,"weights":dict(self.weights),"errors":losses}
    def weighted_margin(self, opinions):
        vals=[]; ws=[]
        for o in opinions:
            if o.fair_margin is not None:
                w=self.weights.get(o.agent,1.0); vals.append(o.fair_margin*w); ws.append(w)
        return sum(vals)/sum(ws) if ws else None
