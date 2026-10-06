from dataclasses import dataclass

@dataclass(frozen=True)
class ModelCandidate:
    version:str
    brier:float
    log_loss:float
    mae_margin:float
    clv_mean:float
    samples:int

class PromotionGate:
    """Requires out-of-sample evidence before a candidate replaces production."""
    def __init__(self,min_samples=250): self.min_samples=min_samples
    def evaluate(self,current:ModelCandidate,candidate:ModelCandidate):
        if candidate.samples<self.min_samples:return False,"insufficient_oos_samples"
        if candidate.brier>current.brier:return False,"brier_regression"
        if candidate.log_loss>current.log_loss:return False,"logloss_regression"
        if candidate.mae_margin>current.mae_margin:return False,"margin_mae_regression"
        if candidate.clv_mean<current.clv_mean-.25:return False,"clv_regression"
        return True,"promotion_eligible"
