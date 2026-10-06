from basketball_omega.market_history import MarketTick, parse_ts, select_snapshot_at_or_before, verified_close, consensus_line

def test_timestamped_market_selection_is_pit_safe():
    ticks=[
        MarketTick("g","spread","home",-4,-110,"a",100,100,"x"),
        MarketTick("g","spread","home",-4.5,-110,"a",110,110,"x"),
        MarketTick("g","spread","home",-5,-110,"a",130,130,"x"),
    ]
    assert select_snapshot_at_or_before(ticks,105).line == -4
    assert verified_close(ticks,125,105).line == -4.5
    assert verified_close(ticks,99,105) is None

def test_consensus_requires_redundancy():
    ticks=[
        MarketTick("g","total","Over",220,-110,"a",100,100,"x"),
        MarketTick("g","total","Over",221,-110,"b",100,100,"x"),
    ]
    assert consensus_line(ticks,100,"total","Over",min_books=2)==220.5
    assert consensus_line(ticks,100,"total","Over",min_books=3) is None

def test_iso_timestamp_parser():
    assert parse_ts("2026-01-01T00:00:00Z") > 0
