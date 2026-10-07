from market_validation_gate import MarketValidationGate


class FakeStore:
    def __init__(self, rows): self.rows = rows
    def predictions_with_outcomes(self): return list(self.rows)


def rows(n=30, market="DOUBLE_CHANCE", selection="X2", p=.72, y=1, odds=1.55):
    return [{
        "model_version":"UMIOS-TITAN-MarketSpecific-v3",
        "market":market, "selection":selection, "predicted_probability":p,
        "outcome":y, "odds":odds
    } for _ in range(n)]


def test_blocks_without_calibration_sample():
    r=MarketValidationGate(FakeStore(rows(29))).evaluate(
        {"market":"DOUBLE_CHANCE","selection":"X2","model_probability":.72,"odds":1.55,
         "validation_evidence":{"market_stress":{"probability_sensitivity":.04},"market_confirmed":True}}
    )
    assert "UMQE_CALIBRATION_SAMPLE_INSUFFICIENT" in r["blockers"]


def test_short_price_requires_band_reliability():
    rs=rows(30,p=.72,y=1,odds=1.55)
    r=MarketValidationGate(FakeStore(rs)).evaluate(
        {"market":"DOUBLE_CHANCE","selection":"X2","model_probability":.72,"odds":1.55,
         "validation_evidence":{"market_stress":{"probability_sensitivity":.04},"market_confirmed":True}}
    )
    assert r["state"] == "PASS"


def test_calibration_failure_blocks():
    rs=rows(30,p=.80,y=0,odds=1.55)
    r=MarketValidationGate(FakeStore(rs)).evaluate(
        {"market":"BTTS","selection":"YES","model_probability":.80,"odds":1.55,
         "validation_evidence":{"market_stress":{"probability_sensitivity":.04},"market_confirmed":True}}
    )
    assert "UMQE_CALIBRATION_GAP_TOO_LARGE" in r["blockers"]


def test_all_market_segments_have_rules():
    gate=MarketValidationGate(FakeStore([]))
    assert gate.ALL_MARKETS.issuperset({
        "1X2","DOUBLE_CHANCE","DNB","BTTS","TOTAL_GOALS","TEAM_GOALS",
        "HANDICAP","CORNERS","CARDS","CORRECT_SCORE","HT","HT_FT"
    })
