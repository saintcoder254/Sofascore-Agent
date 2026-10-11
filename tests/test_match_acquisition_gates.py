"""Regression tests for source matching and acquisition trust preservation."""
from match_acquisition import MatchAcquisitionEngine


def test_team_matching_normalizes_suffixes_and_accents():
    assert MatchAcquisitionEngine._same_team("FC Barcelona", "Barcelona")
    assert MatchAcquisitionEngine._same_team("Atlético Madrid", "Atletico Madrid")


def test_team_matching_rejects_ambiguous_substring_matches():
    # A shared token is not sufficient evidence that two provider records
    # describe the same team; verification must fail closed on ambiguity.
    assert not MatchAcquisitionEngine._same_team("United", "Newcastle United")
    assert not MatchAcquisitionEngine._same_team("City", "Manchester City")


def test_fixture_matching_requires_both_home_and_away_teams():
    target = {"homeTeam": {"name": "FC Barcelona"}, "awayTeam": {"name": "Atletico Madrid"}}
    same = {"homeTeam": {"name": "Barcelona"}, "awayTeam": {"name": "Atlético Madrid"}}
    reversed_fixture = {"homeTeam": {"name": "Atletico Madrid"}, "awayTeam": {"name": "Barcelona"}}
    wrong_away = {"homeTeam": {"name": "Barcelona"}, "awayTeam": {"name": "Real Madrid"}}
    assert MatchAcquisitionEngine._same_fixture(target, same)
    assert not MatchAcquisitionEngine._same_fixture(target, reversed_fixture)
    assert not MatchAcquisitionEngine._same_fixture(target, wrong_away)

