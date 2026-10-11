import unittest

from omega_promotion_gate import OmegaPromotionGate


class TestOmegaPromotionGate(unittest.TestCase):
    def inputs(self, clv_available=20, avg_clv=0.02):
        return {
            "ledger": [{} for _ in range(100)],
            "integrity": [{"valid": True} for _ in range(100)],
            "calibration": {"state": "EVALUATED", "candidate_pass": True},
            "weights": {"models": [{"status": "EARNED"}]},
            "market_benchmark": {"clv_available": clv_available, "avg_clv": avg_clv},
        }

    def test_insufficient_clv_samples_cannot_promote(self):
        args = self.inputs(clv_available=19)
        result = OmegaPromotionGate().evaluate(**args)
        self.assertEqual(result["state"], "SHADOW")
        self.assertIn("INSUFFICIENT_CLV_SAMPLES", result["reasons"])

    def test_nonpositive_clv_cannot_promote(self):
        args = self.inputs(clv_available=20, avg_clv=0.0)
        result = OmegaPromotionGate().evaluate(**args)
        self.assertEqual(result["state"], "SHADOW")
        self.assertIn("MARKET_BENCHMARK_CLV_NOT_POSITIVE", result["reasons"])

    def test_complete_qualifying_evidence_can_promote(self):
        result = OmegaPromotionGate().evaluate(**self.inputs())
        self.assertEqual(result["state"], "PROMOTE")
        self.assertTrue(result["enabled"])


if __name__ == "__main__":
    unittest.main()
