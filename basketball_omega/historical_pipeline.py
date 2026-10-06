"""End-to-end historical training/evaluation entry point for Basketball OMEGA."""
from dataclasses import dataclass
from basketball_omega.historical_dataset import BasketballTrainingExample
from basketball_omega.agents.walk_forward import BasketballWalkForwardTrainer
from basketball_omega.evaluation import EvaluationReport, evaluate
from basketball_omega.promotion import WalkForwardPromotionGate, PromotionDecision

@dataclass(frozen=True)
class HistoricalPipelineResult:
    rows: tuple
    report: EvaluationReport
    promotion: PromotionDecision | None

class BasketballHistoricalPipeline:
    def __init__(self,min_train=50,min_promotion_samples=250):
        self.trainer=BasketballWalkForwardTrainer(min_train=min_train)
        self.gate=WalkForwardPromotionGate(min_samples=min_promotion_samples)

    def run(self,examples,baseline_report=None):
        rows=tuple(self.trainer.run(list(examples)))
        report=evaluate(rows)
        decision=self.gate.evaluate(baseline_report,report) if baseline_report is not None else None
        return HistoricalPipelineResult(rows,report,decision)
