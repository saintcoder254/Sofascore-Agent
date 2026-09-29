from basketball_volatility_guard import BasketballVolatilityGuard
def test_guard_detects_basketball_from_event():
    r=BasketballVolatilityGuard().evaluate({"sport":"basketball"},{"history":{}},{"selection":{"market":"TOTAL_POINTS","selection":"UNDER 177.5","model_probability":0.66}})
    assert r.signals["applicable"] is True
def test_guard_extracts_team_history():
    hist={"home":{"events":[{"homeScore":{"current":90},"awayScore":{"current":100}} for _ in range(6)]}}
    r=BasketballVolatilityGuard().evaluate({"sport":"basketball"},{"history":hist},{"selection":{"market":"TOTAL_POINTS","selection":"UNDER 177.5","model_probability":0.66}})
    assert r.signals["recent_totals_count"]==6
