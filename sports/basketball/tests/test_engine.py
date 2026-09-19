from sports.basketball.engine import BasketballEngine, GameContext, TeamProfile
from sports.basketball.simulation import simulate

def test_projection_is_positive():
    t = TeamProfile(115, 110, 99)
    p = BasketballEngine().project(GameContext(t, t))
    assert p.possessions > 0
    assert p.total_points > 0

def test_monte_carlo_is_reproducible():
    t = TeamProfile(115, 110, 99)
    p = BasketballEngine().project(GameContext(t, t))
    a = simulate(p, simulations=1000, total_line=220, seed=7)
    b = simulate(p, simulations=1000, total_line=220, seed=7)
    assert a.mean_total == b.mean_total
    assert a.over_probability == b.over_probability
