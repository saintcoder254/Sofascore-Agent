from sports.basketball.rotation import RotationPlayer, summarize_rotation

def test_rotation_summary():
    players = [RotationPlayer("a", 32, impact_per_100=5, availability=1, usage=.25),
               RotationPlayer("b", 28, impact_per_100=2, availability=1, usage=.20)]
    result = summarize_rotation(players)
    assert result.expected_impact > 0
    assert 0 < result.continuity <= 1
