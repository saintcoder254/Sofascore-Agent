import unittest
from basketball_omega.agents.player_team_impact import PlayerTeamImpactAgent
from basketball_omega.agents.player_state import PlayerStateAgent
from basketball_omega.agents.minutes_distribution import MinutesDistributionAgent
from basketball_omega.contracts import BasketballContext


class TestBasketballPlayerTeamImpact(unittest.TestCase):
    def test_expected_minutes_weight_strength(self):
        ctx = BasketballContext(
            home="H", away="A",
            players={
                "h1":{"team":"H","expected_minutes":36,"impact_prior":6,"sample_size":100},
                "a1":{"team":"A","expected_minutes":36,"impact_prior":0,"sample_size":100},
            },
        )
        states = {
            "h1": PlayerStateAgent().update(None, 6, 100),
            "a1": PlayerStateAgent().update(None, 0, 100),
        }
        rotations = {
            "H": MinutesDistributionAgent().forecast({"player_id":"h1","expected_minutes":36}),
            "A": MinutesDistributionAgent().forecast({"player_id":"a1","expected_minutes":36}),
        }
        # Build the rotation shape used by the production orchestrator.
        rotations = {
            "H":{"forecasts":{"h1":rotations["H"]}},
            "A":{"forecasts":{"a1":rotations["A"]}},
        }
        out = PlayerTeamImpactAgent().run(ctx, states, rotations, projected_pace=100)
        self.assertGreater(out.fair_margin, 0)
        self.assertIn("team_estimates", out.evidence)

    def test_missing_minutes_raise_uncertainty_not_fixed_penalty(self):
        ctx = BasketballContext(
            home="H", away="A",
            players={
                "h1":{"team":"H","expected_minutes":36,"impact_prior":5,"sample_size":100},
                "a1":{"team":"A","expected_minutes":36,"impact_prior":5,"sample_size":100},
            },
            injuries={"h1":{"status":"questionable","availability_probability":0.5}},
        )
        states = {
            "h1": PlayerStateAgent().update(None, 5, 100),
            "a1": PlayerStateAgent().update(None, 5, 100),
        }
        repl = __import__("basketball_omega.agents.player_replacement", fromlist=["PlayerReplacementAgent"]).PlayerReplacementAgent()
        rotations = {
            "H":repl.estimate([dict(ctx.players["h1"],player_id="h1")],ctx.injuries),
            "A":repl.estimate([dict(ctx.players["a1"],player_id="a1")],{}),
        }
        out = PlayerTeamImpactAgent().run(ctx, states, rotations, projected_pace=100)
        self.assertGreater(out.evidence["uncertainty"], 0)
        self.assertGreater(rotations["H"]["replacement_minutes_needed"], 0)

    def test_untagged_player_is_not_double_counted(self):
        ctx = BasketballContext(
            home="H", away="A",
            players={"x":{"expected_minutes":36,"impact_prior":20,"sample_size":100}},
        )
        state = {"x": PlayerStateAgent().update(None,20,100)}
        repl = {"H":{"forecasts":{}}, "A":{"forecasts":{}}}
        out = PlayerTeamImpactAgent().run(ctx,state,repl,projected_pace=100)
        self.assertEqual(out.fair_margin, 0.0)


if __name__ == "__main__":
    unittest.main()
