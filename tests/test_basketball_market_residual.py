from basketball_omega.clv import verify_clv
from basketball_omega.models.market_residual import MarketResidualEngine
from basketball_omega.promotion_markets import MarketPromotionGate

class R:
    entry_spread=-4.0
    closing_spread=-5.0
    cutoff_at=100.0
    closing_at=99.0

def test_clv_is_unverified_without_enough_timestamped_samples():
    e=verify_clv([R()]*10,min_samples=250)
    assert e.status=="UNVERIFIED"
    assert e.mean_clv is None

def test_residual_engine_uses_market_as_prior():
    x=MarketResidualEngine(0.35).estimate(8.0,-4.0)
    assert x.market_margin==4.0
    assert x.residual==4.0
    assert x.blended_margin==5.4

def test_market_gate_can_promote_totals_independently():
    class M:
        samples=1000; brier=.20; log_loss=.59; margin_mae=9; total_mae=15; clv_samples=1000; clv_mean=.1; chronological=True
    class C:
        samples=1000; brier=.20; log_loss=.59; margin_mae=10; total_mae=14; clv_samples=0; clv_mean=0; chronological=True
    d=MarketPromotionGate(require_clv=False).evaluate("totals",M(),C())
    assert d.eligible
