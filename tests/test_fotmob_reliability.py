import unittest
from unittest.mock import AsyncMock, Mock, patch

from fotmob_adapter import FotMobAdapter
from match_acquisition import MatchAcquisitionEngine


class FotMobReliabilityTests(unittest.TestCase):
    def test_match_list_normalizes_league_nested_matches(self):
        payload = {"leagues": [{"matches": [{
            "id": 123, "home": {"id": 1, "name": "Rapid Wien"},
            "away": {"id": 2, "name": "Austria Wien"},
        }]}]}
        events = FotMobAdapter._extract_events(payload)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["id"], "fotmob:123")
        self.assertEqual(events[0]["homeTeam"]["name"], "Rapid Wien")

    def test_team_name_match_handles_accents_and_club_suffixes(self):
        self.assertTrue(MatchAcquisitionEngine._same_team("Bayern München", "Bayern Munich"))
        self.assertTrue(MatchAcquisitionEngine._same_team("Rapid Wien", "SK Rapid Wien"))
        self.assertFalse(MatchAcquisitionEngine._same_team("Rapid Wien", "Austria Wien"))

    def test_fixture_identity_requires_home_and_away_orientation(self):
        target = {"homeTeam": {"name": "Rapid Wien"}, "awayTeam": {"name": "Austria Wien"}}
        right = {"homeTeam": {"name": "SK Rapid Wien"}, "awayTeam": {"name": "FK Austria Wien"}}
        reversed_fixture = {"homeTeam": {"name": "Austria Wien"}, "awayTeam": {"name": "Rapid Wien"}}
        self.assertTrue(MatchAcquisitionEngine._same_fixture(target, right))
        self.assertFalse(MatchAcquisitionEngine._same_fixture(target, reversed_fixture))

    def test_history_normalizer_rejects_other_sources(self):
        with self.assertRaises(ValueError):
            FotMobAdapter.normalize_team_history({"source": "sofascore", "raw_payload": {}}, "1")

    def test_history_normalizer_extracts_team_fixtures(self):
        raw = {"source": "fotmob", "team_id": "1", "retrieved_at": 10, "raw_payload": {
            "overview": {"fixtures": [{"id": 44, "home": {"id": 1, "name": "Rapid Wien"},
                                      "away": {"id": 2, "name": "Austria Wien"}}]}}}
        result = FotMobAdapter.normalize_team_history(raw, "1")
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["source_event_id"], "44")


if __name__ == "__main__":
    unittest.main()
