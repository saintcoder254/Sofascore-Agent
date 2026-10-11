from historical_failure_gate import HistoricalFailureGate


def test_short_price_home_is_blocked():
    result = HistoricalFailureGate().evaluate(
        {"market": "1X2", "selection": "HOME", "odds": 1.55, "model_probability": 0.64},
        {"selection_justification": "documented value edge"},
    )
    assert result["state"] == "BLOCK"
    assert "F1_FAVORITE_SHORT_PRICE_TRAP" in result["blockers"]


def test_negative_ev_is_blocked():
    result = HistoricalFailureGate().evaluate(
        {"market": "1X2", "selection": "AWAY", "odds": 2.20, "model_probability": 0.40},
        {"selection_justification": "independent models agree"},
    )
    assert "F3_NO_POSITIVE_VALUE" in result["blockers"]


def test_missing_justification_is_blocked():
    result = HistoricalFailureGate().evaluate(
        {"market": "TOTAL_GOALS", "selection": "UNDER_2_5", "odds": 1.60, "model_probability": 0.70}, {}
    )
    assert "F9_SELECTION_JUSTIFICATION_MISSING" in result["blockers"]


def test_all_questions_are_always_returned():
    result = HistoricalFailureGate().evaluate(
        {"market": "BTTS", "selection": "NO", "odds": 1.80, "model_probability": 0.58},
        {"selection_justification": "value supported by independent models"},
    )
    assert len(result["questions"]) == 12


def test_missing_probability_and_odds_fail_closed():
    result = HistoricalFailureGate().evaluate(
        {"market": "DOUBLE_CHANCE", "selection": "X2"},
        {"selection_justification": "historical test"},
    )
    assert "F0_MODEL_PROBABILITY_MISSING" in result["blockers"]
    assert "F0_INVALID_OR_MISSING_ODDS" in result["blockers"]


def test_supplied_edge_conflict_is_blocked():
    result = HistoricalFailureGate().evaluate(
        {"market": "DOUBLE_CHANCE", "selection": "X2", "odds": 1.44,
         "model_probability": 0.715, "edge": 0.10},
        {"selection_justification": "manual retrospective", "confidence_evidence": "strong"},
    )
    assert "F3_EDGE_FIELD_CONFLICTS_WITH_PROBABILITY_AND_PRICE" in result["blockers"]


def test_historical_underperformance_blocks_after_minimum_calibrated_sample():
    result = HistoricalFailureGate().evaluate(
        {"market": "DOUBLE_CHANCE", "selection": "X2", "odds": 1.60, "model_probability": 0.70},
        {
            "selection_justification": "independent evidence and price checked",
            "historical_market_summary": {
                "diagnostic_ready": True,
                "settled_samples": 24,
                "probability_samples": 24,
                "mean_predicted_probability": 0.75,
                "observed_hit_rate": 0.58,
            },
        },
    )
    assert "FH_HISTORICAL_UNDERPERFORMANCE" in result["blockers"]
