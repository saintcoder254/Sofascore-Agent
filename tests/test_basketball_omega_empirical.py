from basketball_omega.models.market_specific import MarketSpecificEngines
from basketball_omega.models.tournament_suite import EmpiricalTournament
from basketball_omega.models.digital_twin import BasketballDigitalTwin

def test_market_suite_has_all_core_markets():
    d={"distribution":{"home_win_probability":.62,"margin_mean":4,"margin_sd":11,"total_mean":224,"total_sd":15},
       "spread":-2.5,"total":220}
    out=MarketSpecificEngines().run(d)
    assert {"moneyline","spread","total","1H","Q1"}<=set(out)

def test_tournament_weights_sum():
    t=EmpiricalTournament(min_samples=2)
    out=t.rank({"a":[{"prob":.6,"outcome":1},{"prob":.6,"outcome":0}],
                "b":[{"prob":.55,"outcome":1},{"prob":.55,"outcome":0}]})
    assert abs(sum(x.weight for x in out)-1)<1e-6

def test_twin_pit_guard():
    t=BasketballDigitalTwin("g",10,{},{"p":{"effective_at":5,"captured_at":9}})
    assert t.assert_pit(10)
