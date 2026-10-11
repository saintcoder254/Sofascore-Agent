from sports.basketball.engine import BasketballEngine, GameContext, TeamProfile
from sports.basketball.simulation import simulate
from sports.basketball.markets import derive_markets

def test_market_probabilities_sum():
    t = TeamProfile(115, 110, 99)
    p = BasketballEngine().project(GameContext(t, t))
    m = derive_markets(simulate(p, simulations=1000, total_line=220, seed=4))
    assert abs(m.home_moneyline + m.away_moneyline - 1.0) < 1e-9
    assert 0 <= m.over <= 1
    assert 0 <= m.under <= 1
