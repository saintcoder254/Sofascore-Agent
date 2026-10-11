import math
from dataclasses import replace
from basketball_omega.evaluation import evaluate
from basketball_omega.promotion import WalkForwardPromotionGate
from basketball_omega.agents.walk_forward import WalkForwardRow
from basketball_omega.agents.opponent_adjustment import OpponentTeammateAdjustmentAgent

def test_metrics_include_brier_logloss_ece_mae_clv():
    rows=[WalkForwardRow(str(i),float(i),.7,.5,200,1,0,198,108,107) for i in range(10)]
    r=evaluate(rows)
    assert r.samples==10 and r.brier<.1 and r.log_loss<1 and r.ece>=0
    assert r.margin_mae==.5 and r.total_mae==2 and r.clv_mean==1

def test_promotion_blocks_regression():
    base=evaluate([WalkForwardRow(str(i),i,.6,0,200,1,0,200,100,99) for i in range(250)])
    bad=replace(base,brier=base.brier+.01)
    d=WalkForwardPromotionGate(min_samples=250).evaluate(base,bad)
    assert not d.eligible and "brier_regression" in d.reasons

def test_adjustment_shrinks_sparse_player():
    a=OpponentTeammateAdjustmentAgent(shrinkage=20)
    out=a.fit([{"player_id":"p1","impact":10,"team_id":"t1","opponent_id":"o1"}])
    assert abs(out["p1"].adjusted_impact) < 10

def test_evaluation_is_chronological():
    rows=[WalkForwardRow("b",2,.5,0,200,1,0,200),WalkForwardRow("a",1,.5,0,200,0,0,200)]
    assert not evaluate(rows).chronological
