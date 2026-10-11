from double_chance_failure_gate import DoubleChanceFailureGate


def stress(**overrides):
    result = {
        "adverse_branch_probability": 0.34,
        "adverse_branch_market": "home_win",
        "probability_sensitivity": 0.06,
        "market_confirmed": True,
    }
    result.update(overrides)
    return {"double_chance_stress": result}


def test_x2_without_stress_is_blocked():
    result = DoubleChanceFailureGate().evaluate(
        {"market": "DOUBLE_CHANCE", "selection": "X2", "model_probability": 0.65, "odds": 1.60}, {}
    )
    assert result["state"] == "BLOCK"
    assert "DC_ADVERSE_BRANCH_NOT_TESTED" in result["blockers"]


def test_x2_with_valid_stress_and_value_can_pass():
    result = DoubleChanceFailureGate().evaluate(
        {"market": "DOUBLE_CHANCE", "selection": "X2", "model_probability": 0.70, "odds": 1.60},
        stress(),
    )
    assert result["state"] == "PASS"


def test_x2_144_fails_edge_and_ev_minimums():
    # Historical pre-match estimate was 71.5%; this is a gate regression, not a claim
    # that the native pipeline produced that estimate.
    result = DoubleChanceFailureGate().evaluate(
        {"market": "DOUBLE_CHANCE", "selection": "X2", "model_probability": 0.715, "odds": 1.44},
        stress(),
    )
    assert result["state"] == "BLOCK"
    assert "DC_EDGE_BELOW_MINIMUM" in result["blockers"]
    assert "DC_EXPECTED_VALUE_BELOW_MINIMUM" in result["blockers"]


def test_wrong_adverse_branch_blocks():
    result = DoubleChanceFailureGate().evaluate(
        {"market": "DOUBLE_CHANCE", "selection": "X2", "model_probability": 0.70, "odds": 1.60},
        stress(adverse_branch_market="away_win"),
    )
    assert "DC_ADVERSE_BRANCH_DOES_NOT_MATCH_SELECTION" in result["blockers"]


def test_missing_edge_field_is_derived_from_price_not_trusted():
    result = DoubleChanceFailureGate().evaluate(
        {"market": "DOUBLE_CHANCE", "selection": "X2", "model_probability": 0.70, "odds": 1.60},
        stress(),
    )
    assert result["inputs"]["derived_probability_edge"] == 0.075
