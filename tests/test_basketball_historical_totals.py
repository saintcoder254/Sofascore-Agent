import unittest
from unittest.mock import patch

from basketball_probability_engine import BasketballProbabilityEngine


class TestBasketballHistoricalTotals(unittest.TestCase):
    def test_variance_uses_within_game_score_plus_concession_totals(self):
        home_scored = [120, 80, 130, 70, 125, 95]
        home_conceded = [110, 100, 115, 90, 120, 105]
        away_scored = [115, 85, 125, 75, 120, 100]
        away_conceded = [110, 95, 115, 90, 115, 100]

        recent_totals = (
            [s + c for s, c in zip(home_scored, home_conceded)][-5:]
            + [s + c for s, c in zip(away_scored, away_conceded)][-5:]
        )
        all_totals = (
            [s + c for s, c in zip(home_scored, home_conceded)]
            + [s + c for s, c in zip(away_scored, away_conceded)]
        )

        engine = BasketballProbabilityEngine()
        event = {
            "id": "variance-test",
            "homeTeam": {"id": 1, "name": "Home"},
            "awayTeam": {"id": 2, "name": "Away"},
        }
        evidence = {"history": {"home": {"events": []}, "away": {"events": []}}}

        with patch.object(
            BasketballProbabilityEngine,
            "_recent_stats",
            side_effect=[
                (home_scored, home_conceded),
                (away_scored, away_conceded),
            ],
        ), patch.object(
            BasketballProbabilityEngine, "_sd", side_effect=[15.0, 20.0]
        ) as sd:
            result = engine._estimate(event, evidence)

        self.assertIsNotNone(result)
        self.assertEqual(sd.call_args_list[0].args[0], recent_totals)
        self.assertEqual(sd.call_args_list[1].args[0], all_totals)
        self.assertEqual(result["sd_total"], 15.0)


if __name__ == "__main__":
    unittest.main()
