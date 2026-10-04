import unittest
from double_chance_failure_gate import DoubleChanceFailureGate

class TestDoubleChanceFailureGate(unittest.TestCase):
    def test_x2_without_stress_is_blocked(self):
        out=DoubleChanceFailureGate().evaluate({"market":"DOUBLE_CHANCE","selection":"X2","model_probability":.65,"odds":1.60,"edge":.04},{})
        self.assertEqual(out["state"],"BLOCK")
        self.assertIn("DC_ADVERSE_BRANCH_NOT_TESTED",out["blockers"])

    def test_x2_with_positive_value_and_stress_can_pass(self):
        evidence={"double_chance_stress":{"adverse_branch_probability":.34,"adverse_branch_market":"home_win","probability_sensitivity":.06,"market_confirmed":True}}
        out=DoubleChanceFailureGate().evaluate({"market":"DOUBLE_CHANCE","selection":"X2","model_probability":.68,"odds":1.60,"edge":.088},evidence)
        self.assertEqual(out["state"],"PASS")

if __name__=="__main__":
    unittest.main()
