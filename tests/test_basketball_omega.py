import unittest
from basketball_omega.contracts import BasketballContext
from basketball_omega.orchestrator import BasketballOmegaOrchestrator

class TestBasketballOmega(unittest.TestCase):
    def test_fusion_returns_verdict(self):
        c = BasketballContext(
            home="H",
            away="A",
            history=[{}] * 20,
            team_stats={
                "H": {"pace": 99, "ortg": 118, "drtg": 110, "three_rate": .40, "tov_forced": .13, "oreb_rate": .25},
                "A": {"pace": 98, "ortg": 112, "drtg": 115, "three_rate": .35, "tov_forced": .12, "oreb_rate": .22},
            },
            market={"spread": -3.0, "total": 225.0},
        )
        v = BasketballOmegaOrchestrator().run(c)
        self.assertIn(v.state, {"NO_BET", "QUALIFIED_CANDIDATE"})
        self.assertIsNotNone(v.fair_margin)
        self.assertGreaterEqual(len(v.agent_opinions), 8)
        self.assertIn("player_state_count", v.audit)

    def test_missing_strength_blocks(self):
        v = BasketballOmegaOrchestrator().run(
            BasketballContext(home="H", away="A", market={"spread": -3.0})
        )
        self.assertEqual(v.state, "NO_BET")
        self.assertIn("fundamental_evidence_gate", v.blocked_reasons)

if __name__ == "__main__":
    unittest.main()
