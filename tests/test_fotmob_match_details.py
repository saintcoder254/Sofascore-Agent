import unittest
from unittest.mock import AsyncMock, Mock, patch

from fotmob_adapter import FotMobAdapter


class TestFotMobMatchDetails(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.adapter = FotMobAdapter()
        self.adapter.client.aclose = AsyncMock()

    async def asyncTearDown(self):
        await self.adapter.close()

    async def test_match_details_preserves_source_and_raw_payload(self):
        response = Mock()
        response.status_code = 200
        response.raise_for_status = Mock()
        response.json = Mock(return_value={"content": {"matchFacts": {"info": []}}})
        self.adapter.client.get = AsyncMock(return_value=response)

        result = await self.adapter.match_details("12345")

        self.assertEqual(result["source"], "fotmob")
        self.assertEqual(result["source_event_id"], "12345")
        self.assertEqual(result["normalization_state"], "RAW_UNNORMALIZED")
        self.assertEqual(result["raw_payload"], {"content": {"matchFacts": {"info": []}}})
        self.adapter.client.get.assert_awaited_once()

    async def test_normalize_match_details_maps_available_sections_and_fails_closed(self):
        raw = {
            "general": {
                "matchId": "12345", "matchName": "Home vs Away",
                "matchTimeUTCDate": "2026-10-10T15:00:00.000Z",
                "homeTeam": {"id": 1, "name": "Home"},
                "awayTeam": {"id": 2, "name": "Away"},
                "leagueName": "Test League",
            },
            "header": {"status": {"started": False, "finished": False}, "teams": []},
            "content": {
                "stats": {"Periods": {"All": {"stats": [
                    {"title": "Possession", "stats": [55, 45]}
                ]}}},
                "lineup": {
                    "homeTeam": {"id": 1, "name": "Home", "starters": [{"name": "H1"}]},
                    "awayTeam": {"id": 2, "name": "Away", "starters": [{"name": "A1"}]},
                },
                "matchFacts": {"events": {"events": [{"type": "Goal", "time": 20}]}},
                "shotmap": {"shots": [{"teamId": 1, "expectedGoals": 0.2}]},
            },
        }
        normalized = self.adapter.normalize_match_details({
            "source": "fotmob", "source_event_id": "12345",
            "retrieved_at": 1000, "raw_payload": raw,
        })
        self.assertEqual(normalized["event"]["id"], "fotmob:12345")
        self.assertEqual(normalized["event"]["homeTeam"]["name"], "Home")
        self.assertEqual(normalized["statistics"]["groups"][0]["title"], "Possession")
        self.assertEqual(normalized["lineups"]["home"]["name"], "Home")
        self.assertEqual(normalized["incidents"]["events"][0]["type"], "Goal")
        self.assertEqual(normalized["shotmap"]["shots"][0]["teamId"], 1)
        self.assertIn("FOTMOB_MARKET_ODDS_UNAVAILABLE", normalized["data_trust"]["hard_blocks"])
        self.assertEqual(normalized["data_trust"]["state"], "QUARANTINED")

    async def test_normalize_match_details_rejects_untrusted_shape(self):
        with self.assertRaises(ValueError):
            self.adapter.normalize_match_details({"source": "sofascore", "raw_payload": {}})

    async def test_match_details_rejects_empty_id(self):
        with self.assertRaises(ValueError):
            await self.adapter.match_details("")


if __name__ == "__main__":
    unittest.main()
