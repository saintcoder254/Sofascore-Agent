import unittest
from league_intelligence_engine import LeagueIntelligenceEngine

class TestLeagueIntelligenceEngine(unittest.TestCase):
    def rows(self, competition, n=40, p=.65, y=1.0, odds=1.8):
        return [{
            "prediction_id": str(i),
            "fixture_id": str(i),
            "market": "1X2",
            "predicted_probability": p,
            "selection": "HOME",
            "odds": odds,
            "closing_odds": 1.70,
            "outcome": y,
            "features": {"competition": competition},
        } for i in range(n)]

    def test_unknown_competition_is_excluded(self):
        rows=self.rows("Premier League") + [{
            "predicted_probability": .5, "outcome": 1, "features": {},
            "market": "1X2", "odds": 2.0
        }]
        out=LeagueIntelligenceEngine().rank(rows)
        self.assertEqual(len(out["ranking"]), 1)
        self.assertEqual(out["ranking"][0]["competition"], "Premier League")

    def test_small_sample_is_not_proven(self):
        out=LeagueIntelligenceEngine(proven_samples=100).rank(self.rows("League One", 20))
        self.assertEqual(out["ranking"][0]["status"], "INSUFFICIENT_SAMPLE")

    def test_positive_price_and_clv_are_reported(self):
        out=LeagueIntelligenceEngine().rank(self.rows("Bundesliga", 100))
        row=out["ranking"][0]
        self.assertGreater(row["avg_expected_value"], 0)
        self.assertGreater(row["avg_clv"], 0)
        self.assertEqual(row["status"], "PROVEN_CANDIDATE")

if __name__ == "__main__":
    unittest.main()
