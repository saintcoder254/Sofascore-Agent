import math
import unittest

from calibration_engine import CalibrationEngine, ModelHealthEngine


class TestCalibrationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CalibrationEngine()

    def test_log_loss_uses_complement_for_negative_outcomes(self):
        rows = [{"p": 0.9, "y": 1}, {"p": 0.1, "y": 0}]
        self.assertAlmostEqual(self.engine.log_loss(rows), -math.log(0.9), places=10)

    def test_reliability_covers_probabilities_below_half_and_one(self):
        rows = [{"p": 0.1, "y": 0}, {"p": 0.4, "y": 1}, {"p": 1.0, "y": 1}]
        result = self.engine.evaluate(rows)
        self.assertEqual(result["samples"], 3)
        self.assertEqual(sum(x["samples"] for x in result["reliability"]), 3)
        self.assertTrue(any(x["low"] == 0.1 for x in result["reliability"]))
        self.assertTrue(any(x["high"] == 1.0 and x["samples"] == 1 for x in result["reliability"]))

    def test_invalid_rows_are_excluded_and_reported(self):
        result = self.engine.evaluate([
            {"p": 0.7, "y": 1}, {"p": 1.2, "y": 0},
            {"p": float("nan"), "y": 0}, {"p": 0.4},
        ])
        self.assertEqual(result["samples"], 1)
        self.assertEqual(result["invalid_rows"], 3)
        self.assertIn("INVALID_VALIDATION_ROWS", ModelHealthEngine().assess(result)["flags"])

    def test_empty_data_is_not_healthy(self):
        result = self.engine.evaluate([])
        self.assertIsNone(result["log_loss"])
        self.assertIn("NO_VALIDATION_SAMPLES", ModelHealthEngine().assess(result)["flags"])


if __name__ == "__main__":
    unittest.main()
