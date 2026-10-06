"""Independent market promotion gates.

Markets are promoted separately. A strong totals model cannot be blocked by a
weak spread model, and no market is promoted without sufficient OOS evidence.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class MarketPromotionDecision:
    market: str
    eligible: bool
    reasons: tuple[str,...]
    samples: int

class MarketPromotionGate:
    def __init__(self,min_samples=250,max_brier_regression=0.0,max_logloss_regression=0.0,
                 max_mae_regression=0.0,min_clv=0.0,require_clv=False):
        self.min_samples=int(min_samples)
        self.max_brier_regression=float(max_brier_regression)
        self.max_logloss_regression=float(max_logloss_regression)
        self.max_mae_regression=float(max_mae_regression)
        self.min_clv=float(min_clv)
        self.require_clv=bool(require_clv)

    def evaluate(self,market,current,candidate):
        reasons=[]
        if candidate.samples < self.min_samples: reasons.append("insufficient_oos_samples")
        if candidate.brier > current.brier+self.max_brier_regression: reasons.append("brier_regression")
        if candidate.log_loss > current.log_loss+self.max_logloss_regression: reasons.append("logloss_regression")
        if candidate.margin_mae > current.margin_mae+self.max_mae_regression: reasons.append("margin_mae_regression")
        if candidate.total_mae > current.total_mae+self.max_mae_regression: reasons.append("total_mae_regression")
        if self.require_clv and (candidate.clv_samples < self.min_samples or candidate.clv_lower_ci is None): reasons.append("clv_unverified")
        elif candidate.clv_lower_ci is not None and candidate.clv_lower_ci <= self.min_clv: reasons.append("clv_ci_not_positive")
        if not candidate.chronological: reasons.append("non_chronological_oos")
        return MarketPromotionDecision(market,not reasons,tuple(reasons),candidate.samples)


    def evaluate_spread(self, current, candidate):
        reasons=[]
        if candidate.samples < self.min_samples: reasons.append("insufficient_oos_samples")
        if candidate.brier > current.brier+self.max_brier_regression: reasons.append("brier_regression")
        if candidate.log_loss > current.log_loss+self.max_logloss_regression: reasons.append("logloss_regression")
        if candidate.margin_mae > current.margin_mae+self.max_mae_regression: reasons.append("margin_mae_regression")
        if self.require_clv and (candidate.clv_samples < self.min_samples or candidate.clv_lower_ci is None): reasons.append("clv_unverified")
        elif candidate.clv_lower_ci is not None and candidate.clv_lower_ci <= self.min_clv: reasons.append("clv_ci_not_positive")
        if not candidate.chronological: reasons.append("non_chronological_oos")
        return MarketPromotionDecision("spread",not reasons,tuple(reasons),candidate.samples)

    def evaluate_totals(self, current, candidate):
        reasons=[]
        if candidate.samples < self.min_samples: reasons.append("insufficient_oos_samples")
        if candidate.total_mae > current.total_mae+self.max_mae_regression: reasons.append("total_mae_regression")
        if candidate.clv_samples and candidate.clv_mean < self.min_clv: reasons.append("negative_clv")
        if not candidate.chronological: reasons.append("non_chronological_oos")
        return MarketPromotionDecision("totals",not reasons,tuple(reasons),candidate.samples)
