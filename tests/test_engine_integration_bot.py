import unittest
from engine_integration_bot import EngineIntegrationBot


class Dummy:
    market_models = object()
    basketball = object()
    regime = object()
    empirical = object()
    dynamic_strength = object()
    competition_regime = object()


class TestEngineIntegrationBot(unittest.TestCase):
    def test_output_detection_and_non_blocking_policy(self):
        report = EngineIntegrationBot().audit(
            probability_engine=Dummy(),
            prediction={
                "state": "QUALIFIED_PREDICTION",
                "market_models": {"probabilities": {"1X2": {"1": 0.4}}},
                "competition_regime": {"label": "normal"},
                "omega_empirical": {"available": True},
                "dynamic_strength": {"available": True},
            },
            analysis={"fixture": "test"},
        )
        states = {item["engine"]: item["state"] for item in report["engines"]}
        self.assertEqual(states["umios_market_models"], "OUTPUT_OBSERVED")
        self.assertEqual(states["empirical_goal_engine"], "OUTPUT_OBSERVED")
        self.assertTrue(report["prediction_preserved"])
        self.assertTrue(report["policy"]["non_blocking"])

    def test_gaps_are_reported_without_veto(self):
        report = EngineIntegrationBot().audit(
            probability_engine=Dummy(),
            prediction={"state": "QUALIFIED_PREDICTION", "selection": {"selection": "1"}},
        )
        self.assertGreater(report["gap_count"], 0)
        self.assertFalse(report["policy"]["missing_engine_output_suppresses_forecast"])


if __name__ == "__main__":
    unittest.main()
