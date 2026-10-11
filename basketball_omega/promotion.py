"""Strict multi-metric model promotion gate."""
from dataclasses import dataclass
from basketball_omega.evaluation import EvaluationReport

@dataclass(frozen=True)
class PromotionDecision:
    eligible:bool
    reasons:tuple[str,...]
    required_samples:int

class WalkForwardPromotionGate:
    def __init__(self,min_samples=250,max_brier_regression=0.0,max_logloss_regression=0.0,max_ece_regression=0.01,max_mae_regression=0.0,min_clv=0.0):
        self.min_samples=int(min_samples); self.max_brier_regression=float(max_brier_regression)
        self.max_logloss_regression=float(max_logloss_regression); self.max_ece_regression=float(max_ece_regression)
        self.max_mae_regression=float(max_mae_regression); self.min_clv=float(min_clv)

    def evaluate(self,current:EvaluationReport,candidate:EvaluationReport):
        reasons=[]
        if candidate.samples<self.min_samples: reasons.append("insufficient_oos_samples")
        if candidate.brier>current.brier+self.max_brier_regression: reasons.append("brier_regression")
        if candidate.log_loss>current.log_loss+self.max_logloss_regression: reasons.append("logloss_regression")
        if candidate.ece>current.ece+self.max_ece_regression: reasons.append("ece_regression")
        if candidate.margin_mae>current.margin_mae+self.max_mae_regression: reasons.append("margin_mae_regression")
        if candidate.total_mae>current.total_mae+self.max_mae_regression: reasons.append("total_mae_regression")
        if candidate.clv_mean<self.min_clv: reasons.append("negative_clv")
        if not candidate.chronological: reasons.append("non_chronological_oos")
        return PromotionDecision(not reasons,tuple(reasons),self.min_samples)
