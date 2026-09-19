from sports.basketball.shot_model import ShotOutcomeModel, ShotProfile

def test_shot_model_points_are_realistic():
    model = ShotOutcomeModel(seed=7)
    profile = ShotProfile()
    points = [model.sample(profile).points for _ in range(2000)]
    assert sum(points) / len(points) < 4
    assert all(0 <= p <= 3 for p in points)

def test_turnover_rate_is_respected_directionally():
    low = ShotOutcomeModel(seed=1)
    high = ShotOutcomeModel(seed=1)
    low_p = ShotProfile(turnover_rate=0.05)
    high_p = ShotProfile(turnover_rate=0.30)
    low_turnovers = sum(low.sample(low_p).turnover for _ in range(5000))
    high_turnovers = sum(high.sample(high_p).turnover for _ in range(5000))
    assert high_turnovers > low_turnovers
