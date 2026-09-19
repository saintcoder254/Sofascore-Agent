from sports.basketball.arbiter import BasketballArbiter, ModelSignal

def test_arbiter_abstains_on_disagreement():
    result = BasketballArbiter().combine([
        ModelSignal("pace", .80, .9, 1.0),
        ModelSignal("shot", .45, .9, 1.0),
    ])
    assert result.decision == "NO_BET"

def test_arbiter_accepts_consensus():
    result = BasketballArbiter().combine([
        ModelSignal("pace", .72, .9, 1.0),
        ModelSignal("shot", .74, .8, 1.0),
        ModelSignal("rotation", .71, .8, .9),
    ])
    assert result.decision == "BET"
