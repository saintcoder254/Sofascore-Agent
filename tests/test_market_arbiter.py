from market_arbiter import MarketArbiter

def pred(sel,odds,p,probs,sample=10):
    return {"selection":{"market":"TOTAL_GOALS","selection":sel,"odds":odds,"model_probability":p,"edge":p-1/odds,"expected_value":p*odds-1},"probabilities":{"TOTAL_GOALS":probs},"history":{"home_games":sample,"away_games":sample}}

def ev(n=2):
    return {"odds":{f"book{i}":{"markets":[{"name":"Over/Under","choices":[{"name":"Over 2.5","decimalValue":2.0},{"name":"Under 2.5","decimalValue":1.8},{"name":"Over 3.5","decimalValue":2.2},{"name":"Under 3.5","decimalValue":1.4}]}]} for i in range(n)}}

def test_under_tail_blocks():
    r=MarketArbiter().evaluate(pred("Under 2.5",1.48,.70,{"OVER 2.5":.30,"UNDER 2.5":.70}),ev())
    assert r["state"]=="BLOCK" and "UNDER_UPPER_TAIL_TOO_LARGE" in r["reasons"]

def test_short_over_blocks():
    r=MarketArbiter().evaluate(pred("Over 2.5",1.18,.86,{"OVER 2.5":.86,"UNDER 2.5":.14}),ev())
    assert r["state"]=="BLOCK" and "VERY_SHORT_PRICE_REQUIRES_P>=0.90" in r["reasons"]

def test_source_gate():
    r=MarketArbiter().evaluate(pred("Under 3.5",1.40,.76,{"OVER 3.5":.24,"UNDER 3.5":.76}),ev(1))
    assert r["state"]=="BLOCK" and "INSUFFICIENT_INDEPENDENT_MARKET_SOURCES" in r["reasons"]

def test_valid_total_passes():
    r=MarketArbiter().evaluate(pred("Under 2.5",1.60,.72,{"OVER 2.5":.14,"UNDER 2.5":.86}),ev())
    assert r["state"]=="PASS"

def test_short_price_gate():
    r=MarketArbiter().evaluate(pred("Under 2.5",1.28,.83,{"OVER 2.5":.12,"UNDER 2.5":.88}),ev())
    assert r["state"]=="BLOCK" and "SHORT_PRICE_REQUIRES_P>=0.85" in r["reasons"]


def test_double_chance_missing_edge_and_ev_are_derived_and_blocked_when_thin():
    prediction = {
        "selection": {"market": "DOUBLE_CHANCE", "selection": "X2",
                      "odds": 1.44, "model_probability": 0.715},
        "history": {"home_games": 10, "away_games": 10},
    }
    result = MarketArbiter().evaluate(prediction, {})
    assert result["state"] == "BLOCK"
    assert "EDGE_BELOW_GATE" in result["reasons"]
    assert "EV_BELOW_GATE" in result["reasons"]
    assert abs(result["edge"] - (0.715 - 1 / 1.44)) < 1e-9
    assert abs(result["expected_value"] - (0.715 * 1.44 - 1)) < 1e-9


def test_double_chance_conflicting_supplied_edge_is_blocked():
    prediction = {
        "selection": {"market": "DOUBLE_CHANCE", "selection": "X2",
                      "odds": 1.60, "model_probability": 0.70,
                      "edge": 0.20, "expected_value": 0.12},
        "history": {"home_games": 10, "away_games": 10},
    }
    result = MarketArbiter().evaluate(prediction, {})
    assert "EDGE_FIELD_CONFLICTS_WITH_PROBABILITY_AND_PRICE" in result["reasons"]
