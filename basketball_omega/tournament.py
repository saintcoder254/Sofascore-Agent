from dataclasses import dataclass
from .evaluation import EvaluationReport
from .promotion import WalkForwardPromotionGate

@dataclass(frozen=True)
class TournamentResult:
    candidate:str
    baseline:str
    candidate_report:EvaluationReport
    baseline_report:EvaluationReport
    promoted:bool
    reasons:tuple

class WalkForwardTournament:
    """Tournament runner: all candidates consume identical chronological OOS rows."""
    def __init__(self, gate=None): self.gate=gate or WalkForwardPromotionGate(min_samples=250)
    def run(self,candidates,baseline,evaluator):
        base=evaluator(baseline)
        results=[]
        for name,model in candidates.items():
            report=evaluator(model)
            decision=self.gate.evaluate(base,report)
            results.append(TournamentResult(name,baseline,report,base,decision.eligible,decision.reasons))
        results.sort(key=lambda x:(x.promoted,-x.candidate_report.brier,x.candidate_report.log_loss))
        return results
