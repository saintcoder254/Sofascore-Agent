from basketball_probability_engine import BasketballProbabilityEngine
def event(): return {"id":"1","sport":"basketball","homeTeam":{"id":"H"},"awayTeam":{"id":"A"}}
def game(i,h,a): return {"status":{"type":{"state":"finished"}},"homeTeam":{"id":"H"},"awayTeam":{"id":"A"},"homeScore":{"current":h},"awayScore":{"current":a}}
def test_basketball_engine_rejects_thin_history():
    e=event(); evidence={"history":{"home":{"events":[game(i,80+i,75) for i in range(2)]},"away":{"events":[game(i,82,78+i) for i in range(2)]}}}
    assert BasketballProbabilityEngine().run(e,evidence,{"state":"QUALIFIED"})["state"]=="NO_BET"
def test_basketball_engine_is_not_goal_poisson():
    e=event(); evidence={"history":{"home":{"events":[game(i,90+i%3,82) for i in range(8)]},"away":{"events":[game(i,88,84+i%2) for i in range(8)]}}}
    r=BasketballProbabilityEngine(simulations=5000).run(e,evidence,{"state":"QUALIFIED"})
    assert r["model"].startswith("UMIOS-BASKETBALL-FUSION") and "expected_points" in r
