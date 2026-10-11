import unittest

from validation_method_swarm import (
    AgentBus,
    ValidationSwarmRequest,
    bayesian_update_bot,
    convergence_bot,
    market_benchmark_bot,
    poisson_market_probabilities,
    run_validation_swarm,
)


class ValidationMethodSwarmTests(unittest.TestCase):
    def test_poisson_probabilities_are_bounded(self):
        probs = poisson_market_probabilities(1.4, 1.1)
        self.assertEqual(set(probs), {"home", "draw", "away", "over_2_5", "btts_yes"})
        self.assertTrue(all(0 <= p <= 1 for p in probs.values()))
        self.assertAlmostEqual(sum(probs[k] for k in ("home", "draw", "away")), 1.0, places=6)

    def test_missing_samples_are_not_fabricated(self):
        result = run_validation_swarm(ValidationSwarmRequest(
            fixture_id="test-fixture",
            expected_goals_home=1.4,
            expected_goals_away=1.1,
        ))
        self.assertEqual(result["bots"]["bootstrap"]["status"], "UNAVAILABLE")
        self.assertEqual(result["bots"]["convergence"]["status"], "UNAVAILABLE")
        self.assertEqual(result["production_bet_certification"], "NOT_GRANTED")
        self.assertGreater(result["communication"]["message_count"], 5)

    def test_market_bot_normalizes_overround_and_sends_message(self):
        bus = AgentBus("test")
        model = poisson_market_probabilities(1.3, 1.0)
        result = market_benchmark_bot({"home": 2.2, "draw": 3.2, "away": 3.4}, model, bus)
        self.assertEqual(result["status"], "PASS")
        self.assertAlmostEqual(sum(result["normalized_market_probabilities"].values()), 1.0)
        inbox = bus.inbox("bayesian_update_bot", "market_prior_signal")
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0].sender, "market_benchmark_bot")

    def test_bayesian_bot_only_uses_valid_explicit_likelihood_ratios(self):
        bus = AgentBus("test")
        result = bayesian_update_bot(
            {"home": .5, "draw": .25, "away": .25},
            [
                {"outcome": "home", "likelihood_ratio": 2.0, "source": "verified-test"},
                {"outcome": "away", "likelihood_ratio": -3.0, "source": "invalid"},
            ],
            bus,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertGreater(result["posterior_1x2"]["home"], .5)
        self.assertAlmostEqual(sum(result["posterior_1x2"].values()), 1.0)
        self.assertEqual(len(result["audit"][0]["evidence_applied"]), 1)

    def test_convergence_requires_two_real_batches(self):
        bus = AgentBus("test")
        result = convergence_bot(["home", "draw", "away"], 1000, bus)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["n"], 3)

    def test_bad_market_odds_block(self):
        bus = AgentBus("test")
        result = market_benchmark_bot({"home": 1.0, "draw": 3.0, "away": 4.0}, {"home": .5, "draw": .25, "away": .25}, bus)
        self.assertEqual(result["status"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
