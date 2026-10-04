from historical_failure_gate import HistoricalFailureGate

def test_short_price_home_is_blocked():
    r=HistoricalFailureGate().evaluate({"market":"1X2","selection":"HOME","odds":1.55,"model_probability":0.64},{"selection_justification":"documented value edge"})
    assert r["state"]=="BLOCK"
    assert "F1_FAVORITE_SHORT_PRICE_TRAP" in r["blockers"]

def test_negative_ev_is_blocked():
    r=HistoricalFailureGate().evaluate({"market":"1X2","selection":"AWAY","odds":2.20,"model_probability":0.40},{"selection_justification":"independent models agree"})
    assert "F3_NO_POSITIVE_VALUE" in r["blockers"]

def test_missing_justification_is_blocked():
    r=HistoricalFailureGate().evaluate({"market":"TOTAL_GOALS","selection":"UNDER_2_5","odds":1.60,"model_probability":0.70},{})
    assert "F9_SELECTION_JUSTIFICATION_MISSING" in r["blockers"]

def test_all_questions_are_always_returned():
    r=HistoricalFailureGate().evaluate({"market":"BTTS","selection":"NO","odds":1.80,"model_probability":0.58},{"selection_justification":"value supported by independent models"})
    assert len(r["questions"])==12
