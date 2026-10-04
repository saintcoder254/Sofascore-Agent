import unittest
from empirical_goal_engine import EmpiricalGoalEngine

class TestEmpiricalGoalEngine(unittest.TestCase):
    def test_missing_history_is_explicit(self):
        e=EmpiricalGoalEngine(simulations=10000)
        out=e.run({"id":"x","homeTeam":{"id":"1"},"awayTeam":{"id":"2"}},{"history":{}})
        self.assertFalse(out["available"])

    def test_empirical_hybrid_is_available(self):
        def game(hid,aid,h,a):
            return {"status":{"type":{"state":"finished"}},"homeTeam":{"id":str(hid)},"awayTeam":{"id":str(aid)},"homeScore":{"current":h},"awayScore":{"current":a}}
        home=[game(1,9,2,0),game(1,8,1,0),game(7,1,0,1),game(1,6,3,1)]
        away=[game(9,2,0,1),game(8,2,1,2),game(2,7,2,0),game(2,6,1,1)]
        evidence={"history":{"home":{"events":home},"away":{"events":away}}}
        out=EmpiricalGoalEngine(simulations=10000).run({"id":"x","homeTeam":{"id":"1"},"awayTeam":{"id":"2"}},evidence)
        self.assertTrue(out["available"])
        self.assertIn("BTTS",out["hybrid_markets"])
        self.assertGreater(sum(out["hybrid_markets"]["1X2"].values()),0.99)

if __name__=="__main__":
    unittest.main()
