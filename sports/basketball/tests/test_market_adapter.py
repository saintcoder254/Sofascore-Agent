from sports.basketball.market_adapter import BasketballMarketAdapter

def test_market_adapter_ignores_bad_quotes():
    rows = BasketballMarketAdapter().normalize("1", "test", {
        "quotes": [
            {"market": "total", "selection": "over", "odds": 1.90},
            {"market": "total", "selection": "under", "odds": "bad"},
        ]
    }, 1.0)
    assert len(rows) == 1
