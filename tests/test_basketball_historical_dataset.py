import unittest
from basketball_omega.data_schema import BasketballSnapshot, TeamSnapshot, PlayerSnapshot, MarketSnapshot
from basketball_omega.historical_dataset import BasketballPITDatasetBuilder


class TestBasketballPITDataset(unittest.TestCase):
    def test_future_player_and_market_are_excluded(self):
        s = BasketballSnapshot(
            fixture_id="G1", captured_at=200,
            home_team_id="H", away_team_id="A",
            teams={
                "H": TeamSnapshot("H","Home",100,{"ortg":118}),
                "A": TeamSnapshot("A","Away",100,{"ortg":112}),
            },
            players={
                "p1": PlayerSnapshot("p1","H",100,{"impact":4},expected_minutes=30),
                "p2": PlayerSnapshot("p2","H",200,{"impact":20},expected_minutes=40),
            },
            markets=[
                MarketSnapshot("G1",100,"spread",-2.5,-110,"H","book",is_opening=True),
                MarketSnapshot("G1",200,"spread",-5.5,-110,"H","book",is_closing=True),
            ],
        )
        row = BasketballPITDatasetBuilder().build_example(s,150,1,5,220,300)
        self.assertIn("p1",row.features["players"])
        self.assertNotIn("p2",row.features["players"])
        self.assertEqual(len(row.features["markets"]),1)

    def test_outcome_cannot_precede_cutoff(self):
        s = BasketballSnapshot("G2",100,"H","A")
        with self.assertRaises(ValueError):
            BasketballPITDatasetBuilder().build_example(s,150,1,1,200,150)


if __name__ == "__main__":
    unittest.main()
