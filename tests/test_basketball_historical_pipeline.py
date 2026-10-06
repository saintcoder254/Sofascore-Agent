from basketball_omega.historical_pipeline import BasketballHistoricalPipeline
from basketball_omega.evaluation import EvaluationReport

def test_pipeline_requires_real_oos_rows_for_promotion():
    pipe=BasketballHistoricalPipeline(min_train=2,min_promotion_samples=3)
    assert pipe.run([]).report.samples == 0
