import unittest
from basketball_omega.agents.player_state import PlayerStateAgent,PlayerState
from basketball_omega.agents.minutes_distribution import MinutesDistributionAgent
from basketball_omega.agents.lineup_interaction import LineupInteractionAgent
from basketball_omega.agents.player_replacement import PlayerReplacementAgent

class TestBasketballPlayerState(unittest.TestCase):
 def test_kalman_update_moves_toward_observation_and_reduces_variance(self):
  a=PlayerStateAgent()
  s=PlayerState("p",0,9,10)
  n=a.update(s,6,1)
  self.assertGreater(n.impact,s.impact); self.assertLess(n.variance,s.variance)

 def test_minutes_uncertainty_for_questionable(self):
  f=MinutesDistributionAgent().forecast({"player_id":"p","expected_minutes":34},{"status":"questionable"})
  self.assertLess(f.availability_probability,1); self.assertLess(f.mean,34); self.assertGreater(f.high-f.low,0)

 def test_five_man_interaction_shrinks_sparse_pairs(self):
  ids=["1","2","3","4","5"]
  x=LineupInteractionAgent().estimate("T",ids,{})
  self.assertEqual(x.synergy,0); self.assertGreaterEqual(x.uncertainty,0)

 def test_replacement_chain_excludes_out_player(self):
  players=[{"player_id":"out","expected_minutes":30},{"player_id":"a","expected_minutes":20,"replacement_priority":3},{"player_id":"b","expected_minutes":15,"replacement_priority":2}]
  r=PlayerReplacementAgent().estimate(players,{"out":{"status":"out"}})
  self.assertIn("out",r["replacement_chain"]); self.assertNotIn("out",r["replacement_chain"]["out"])

if __name__=="__main__": unittest.main()
