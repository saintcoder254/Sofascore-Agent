from basketball_omega.models.impact import RidgeRAPM
from basketball_omega.models.minutes_model import MinutesForecaster
from basketball_omega.models.independence import IndependenceWeightLearner
from basketball_omega.models.distribution import BasketballDistributionEngine
from basketball_omega.models.market_engines import MarketEngineSuite
from basketball_omega.models.calibration_suite import CalibrationSuite

def test_rapm_fits():
    m=RidgeRAPM().fit([{"home_players":["a"],"away_players":["b"],"target":4},
                       {"home_players":["a"],"away_players":["b"],"target":4}])
    assert "a" in m.coef

def test_minutes_out_is_zero():
    f=MinutesForecaster().forecast("a",[{"minutes":30},{"minutes":31}],"out")
    assert f.mean==0

def test_independence_weights_sum():
    rows=[{"name":"a","prob":.7,"outcome":1},{"name":"b","prob":.6,"outcome":1}]*20
    w=IndependenceWeightLearner().fit(rows)
    assert abs(sum(x.weight for x in w)-1)<1e-6

def test_distribution():
    d=BasketballDistributionEngine().simulate(99,115,112,sims=300)
    assert d.home_mean>0 and 0<=d.home_win_probability<=1

def test_calibration():
    r=CalibrationSuite().evaluate([.7,.8,.2,.1],[1,1,0,0])
    assert r.samples==4 and r.brier<.1
