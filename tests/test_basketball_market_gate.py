import unittest

from sports.basketball.market_gate import total_gate


class TotalMarketGateTests(unittest.TestCase):
    def test_low_line_over_is_penalized_and_can_be_rejected(self):
        result = total_gate(
            side="over",
            line=155.5,
            projection_total=161.0,
            uncertainty=12.0,
            market_probability=0.625,
            data_quality=0.95,
            regime="neutral",
            opponent_projection=72.0,
        )
        self.assertIn("low_line_over_penalty", result.reasons)
        self.assertFalse(result.passed)

    def test_robust_edge_is_required(self):
        result = total_gate(
            side="under",
            line=184.5,
            projection_total=176.0,
            uncertainty=8.0,
            market_probability=0.645,
            data_quality=0.95,
            regime="neutral",
            opponent_projection=92.0,
        )
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.robust_probability - 0.645, 0.055)


if __name__ == "__main__":
    unittest.main()
