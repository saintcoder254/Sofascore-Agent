from sports.basketball.feature_builder import build_rolling_features

def test_feature_builder_uses_finished_games_only():
    events = [
        {"status": {"type": "finished"}, "homeTeam": {"id": 1}, "awayTeam": {"id": 2},
         "homeScore": {"current": 100}, "awayScore": {"current": 90}},
        {"status": {"type": "notstarted"}, "homeTeam": {"id": 1}, "awayTeam": {"id": 3},
         "homeScore": {}, "awayScore": {}},
    ]
    result = build_rolling_features(events, 1)
    assert result.games == 1
    assert result.points_for == 100
    assert result.points_against == 90
