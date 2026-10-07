from basketball_probability_engine import BasketballProbabilityEngine

def test_possession_efficiency_path():
    e={"id":"1","sport":"basketball","homeTeam":{"id":"H"},"awayTeam":{"id":"A"}}
    def g(i):
        return {"status":{"type":{"state":"finished"}},"homeTeam":{"id":"H"},"awayTeam":{"id":"A"},
                "homeScore":{"current":88+i%2},"awayScore":{"current":82+i%2},
                "statistics":{"H":{"FGA":78,"ORB":10,"TO":12,"FTA":18},
                               "A":{"FGA":76,"ORB":9,"TO":13,"FTA":17}}}
    ev={"history":{"home":{"events":[g(i) for i in range(8)]},
                   "away":{"events":[g(i) for i in range(8)]}}}
    r=BasketballProbabilityEngine(simulations=5000).run(e,ev,{"state":"QUALIFIED"})
    assert r["model_path"]=="possession_efficiency"
    assert r["expected_possessions"] is not None
    assert r["history"]["efficiency_games"]>=5
    assert r["production_eligible"] is True

def test_no_box_score_keeps_score_form_path():
    e={"id":"1","sport":"basketball","homeTeam":{"id":"H"},"awayTeam":{"id":"A"}}
    def g(i):
        return {"status":{"type":{"state":"finished"}},"homeTeam":{"id":"H"},"awayTeam":{"id":"A"},
                "homeScore":{"current":90+i%3},"awayScore":{"current":82+i%2}}
    ev={"history":{"home":{"events":[g(i) for i in range(8)]},
                   "away":{"events":[g(i) for i in range(8)]}}}
    r=BasketballProbabilityEngine(simulations=5000).run(e,ev,{"state":"QUALIFIED"})
    assert r["model_path"]=="score_form"
    assert r["expected_possessions"] is None


def test_score_form_fallback_is_shadow_only():
    e={"id":"2","sport":"basketball","homeTeam":{"id":"H"},"awayTeam":{"id":"A"}}
    def g(i):
        return {"status":{"type":{"state":"finished"}},
                "homeTeam":{"id":"H"},"awayTeam":{"id":"A"},
                "homeScore":{"current":110+i%3},"awayScore":{"current":95+i%2}}
    ev={"history":{"home":{"events":[g(i) for i in range(8)]},
                   "away":{"events":[g(i) for i in range(8)]}}}
    r=BasketballProbabilityEngine(simulations=5000).run(e,ev,{"state":"QUALIFIED"})
    assert r["model_path"]=="score_form"
    assert r["production_eligible"] is False
    assert r["fallback_reason"]=="INSUFFICIENT_VERIFIED_POSSESSION_EFFICIENCY_HISTORY"
    assert r["selection"] is None
    assert r["state"]=="NO_BET"
