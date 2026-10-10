from omega_promotion_gate import OmegaPromotionGate


def _inputs(clv_available=50, avg_clv=0.01, oos_ready=True):
    ledger=[{"id":i} for i in range(250)]
    integrity=[{"valid":True}]
    calibration={"state":"EVALUATED","candidate_pass":True}
    weights={"models":[{"model":"model-a","status":"EARNED"}]}
    benchmark={
        "state":"PASSED",
        "clv_available":clv_available,
        "avg_clv":avg_clv,
        "by_market":{"TOTAL":{"clv_available":clv_available,"avg_clv":avg_clv}},
    }
    oos={
        "state":"EVALUATED",
        "promotion_ready":oos_ready,
        "promotion_ready_models":[{"model":"model-a","market":"TOTAL"}] if oos_ready else [],
    }
    return ledger, integrity, calibration, weights, benchmark, oos


def test_promotion_requires_verified_clv():
    out=OmegaPromotionGate().evaluate(*_inputs(clv_available=49, avg_clv=0.50))
    assert out["state"]=="SHADOW"
    assert "INSUFFICIENT_VERIFIED_CLV_SAMPLES" in out["reasons"]


def test_promotion_requires_positive_clv():
    out=OmegaPromotionGate().evaluate(*_inputs(clv_available=50, avg_clv=0.0))
    assert out["state"]=="SHADOW"
    assert "MARKET_BENCHMARK_CLV_NOT_POSITIVE" in out["reasons"]


def test_promotion_requires_oos_linkage():
    out=OmegaPromotionGate().evaluate(*_inputs(oos_ready=False))
    assert out["state"]=="SHADOW"
    assert "OOS_WALK_FORWARD_GATE_NOT_PASSED" in out["reasons"]


def test_promotion_can_pass_only_after_all_hard_gates():
    out=OmegaPromotionGate().evaluate(*_inputs())
    assert out["state"]=="PROMOTE"
    assert out["enabled"] is True
