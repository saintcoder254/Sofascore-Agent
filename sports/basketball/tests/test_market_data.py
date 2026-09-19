from sports.basketball.market_data import remove_vig, decimal_to_implied

def test_remove_vig_sums_to_one():
    result = remove_vig({"home": 1.90, "away": 1.90})
    assert abs(sum(result.values()) - 1.0) < 1e-9

def test_implied_probability():
    assert abs(decimal_to_implied(2.0) - .5) < 1e-9
