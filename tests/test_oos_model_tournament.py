import unittest
from oos_model_tournament import OOSModelTournament


class TestOOSTournament(unittest.TestCase):
    def rows(self, model, market="1X2", n=835, bias=0.0):
        return [
            {
                "predicted_at": i,
                "fixture_id": f"{market}-f{i}",
                "market": market,
                "p": min(.99, max(.01, .55 + bias + (i % 2) * .1)),
                "y": 1.0 if i % 3 else 0.0,
                "model": model,
            }
            for i in range(n)
        ]

    def test_insufficient_test_data_shadows(self):
        out = OOSModelTournament(min_train=50, min_test=20).run({"a": self.rows("a", n=60)})
        self.assertEqual(out["models"]["a"]["state"], "SHADOW")
        self.assertFalse(out["promotion_ready"])

    def test_evaluates_expanding_walk_forward(self):
        out = OOSModelTournament(min_train=50, min_test=20).run({"a": self.rows("a")})
        self.assertEqual(out["models"]["a"]["state"], "EVALUATED")
        self.assertEqual(out["models"]["a"]["train_samples"], 175)
        self.assertEqual(out["models"]["a"]["test_samples"], 500)
        self.assertEqual(out["market_results"]["a"]["1X2"]["window_count"], 2)
        self.assertTrue(out["market_results"]["a"]["1X2"]["walk_forward_pass"])
        self.assertIn({"model": "a", "market": "1X2"}, out["promotion_ready_models"])

    def test_markets_are_not_pooled(self):
        rows = self.rows("a", market="TOTAL", n=835) + self.rows("a", market="ML", n=835)
        out = OOSModelTournament().run({"a": rows})
        self.assertEqual(set(out["market_results"]["a"]), {"ML", "TOTAL"})
        self.assertIn({"model": "a", "market": "ML"}, out["promotion_ready_models"])
        self.assertIn({"model": "a", "market": "TOTAL"}, out["promotion_ready_models"])


if __name__ == "__main__":
    unittest.main()
