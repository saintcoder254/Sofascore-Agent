"""Regression tests for current FotMob match-list contract."""
import asyncio

from fotmob_adapter import FotMobAdapter


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "date": "20261010",
            "leagues": [{
                "name": "Test League",
                "matches": [{
                    "id": 123,
                    "home": {"id": 1, "name": "Home FC", "score": None},
                    "away": {"id": 2, "name": "Away FC", "score": None},
                    "status": {"started": False, "finished": False},
                }],
            }],
        }


class FakeClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append((url, params))
        return FakeResponse()

    async def aclose(self):
        return None


def test_fotmob_uses_matches_endpoint_and_parses_league_grouped_events():
    async def run():
        adapter = FotMobAdapter(timeout=1)
        fake = FakeClient()
        adapter.client = fake
        try:
            payload = await adapter.events_for_date("2026-10-10")
        finally:
            await adapter.close()
        assert fake.calls == [
            ("https://www.fotmob.com/api/data/matches", {"date": "20261010"})
        ]
        assert len(payload["events"]) == 1
        event = payload["events"][0]
        assert event["id"] == "fotmob:123"
        assert event["homeTeam"]["name"] == "Home FC"
        assert event["awayTeam"]["name"] == "Away FC"
        assert event["status"]["finished"] is False

    asyncio.run(run())
