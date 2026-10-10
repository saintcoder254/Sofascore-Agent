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

    async def test_match_details_rejects_empty_id(self):
        with self.assertRaises(ValueError):
            await self.adapter.match_details("")


if __name__ == "__main__":
    unittest.main()
