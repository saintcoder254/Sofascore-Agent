import unittest

from calibration_pipeline import CalibrationPipeline


class TestCalibrationPipeline(unittest.TestCase):
    def rows(self, n=100):
        return [
            {"predicted_at": i, "p": 0.2 + (i % 8) * 0.1, "y": 1.0 if i % 3 else 0.0}
            for i in range(n)
        ]

    def test_only_valid_settled_rows_are_evaluated(self):
        rows = self.rows(100)
        rows += [
            {"predicted_at": 101, "p": 0.8},  # unsettled: no outcome
            {"predicted_at": 102, "p": 1.4, "y": 1.0},
            {"predicted_at": 103, "p": 0.5, "y": 0.0},
        ]
        out = CalibrationPipeline().run(rows)
        self.assertEqual(out["state"], "EVALUATED")
        self.assertEqual(out["samples"], 101)
        self.assertEqual(out["invalid_rows"], 2)
        self.assertFalse(out["live_adjustment"])

    def test_insufficient_rows_remain_shadow(self):
        out = CalibrationPipeline().run(self.rows(60))
        self.assertEqual(out["state"], "SHADOW")
        self.assertEqual(out["reason"], "INSUFFICIENT_SETTLED_VALID_ROWS")
        self.assertFalse(out["live_adjustment"])

    def test_walk_forward_split_is_chronological(self):
        out = CalibrationPipeline().run(self.rows(100))
        self.assertEqual(out["train_samples"], 70)
        self.assertEqual(out["test_samples"], 30)
        self.assertEqual(out["state"], "EVALUATED")


if __name__ == "__main__":
    unittest.main()
