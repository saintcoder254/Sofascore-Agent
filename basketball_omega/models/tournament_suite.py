from dataclasses import dataclass
from .calibration_suite import CalibrationSuite
from .independence import IndependenceWeightLearner
from ..promotion import WalkForwardPromotionGate

@dataclass(frozen=True)
class CandidateScore:
    name:str
    brier:float
    log_loss:float
    ece:float
    samples:int
    weight:float

class EmpiricalTournament:
    """Runs identical chronological OOS observations through every candidate."""
    def __init__(self,min_samples=250):
        self.cal=CalibrationSuite()
        self.weights=IndependenceWeightLearner()
        self.gate=WalkForwardPromotionGate(min_samples=min_samples)

    def score(self,name,probs,outcomes):
        r=self.cal.evaluate(probs,outcomes)
        return CandidateScore(name,r.brier,r.log_loss,r.ece,r.samples,0.0)

    def rank(self,candidates):
        # candidates: {name:[{prob,outcome}]}
        rows=[]
        flat=[]
        for name,data in candidates.items():
            probs=[x["prob"] for x in data]; outcomes=[x["outcome"] for x in data]
            rows.append(self.score(name,probs,outcomes))
            flat.extend({"name":name,"prob":p,"outcome":y} for p,y in zip(probs,outcomes))
        ws={x.name:x.weight for x in self.weights.fit(flat)}
        return [CandidateScore(x.name,x.brier,x.log_loss,x.ece,x.samples,ws.get(x.name,0)) for x in rows]
