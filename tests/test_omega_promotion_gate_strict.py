from omega_promotion_gate import OmegaPromotionGate


def _inputs(clv_available=50, avg_clv=0.01):
    ledger=[{"id":i} for i in range(250)]
    integrity=[{"valid":True}]
    calibration={"state":"EVALUATED","candidate_pass":True}
    weights={"models":[{"status":"EARNED"}]}
    benchmark={"state":"PASSED","clv_available":clv_available,"avg_clv":avg_clv}
    return ledger, integrity, calibration, weights, benchmark


def test_promotion_requires_verified_clv():
    gate=OmegaPromotionGate()
    args=_inputs(clv_available=49, avg_clv=0.50)
    out=gate.evaluate(*args)
    assert out["state"]=="SHADOW"
    assert "INSUFFICIENT_VERIFIED_CLV_SAMPLES" in out["reasons"]


def test_promotion_requires_positive_clv():
    gate=OmegaPromotionGate()
    args=_inputs(clv_available=50, avg_clv=0.0)
    out=gate.evaluate(*args)
    assert out["state"]=="SHADOW"
    assert "MARKET_BENCHMARK_CLV_NOT_POSITIVE" in out["reasons"]


def test_promotion_can_pass_only_after_all_hard_gates():
    gate=OmegaPromotionGate()
    args=_inputs(clv_available=50, avg_clv=0.01)
    out=gate.evaluate(*args)
    assert out["state"]=="PROMOTE"
    assert out["enabled"] is True
