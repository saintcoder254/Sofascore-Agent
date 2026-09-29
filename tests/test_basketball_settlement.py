from result_verifier import ResultVerifierAgent

def test_basketball_total_settlement():
    row={"market":"TOTAL_POINTS","selection":"UNDER 177.5"}
    assert ResultVerifierAgent.settle(row,{"home":80,"away":90})==1.0
    assert ResultVerifierAgent.settle(row,{"home":100,"away":90})==0.0
