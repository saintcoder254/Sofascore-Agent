import unittest

from umios_arbiter import UMIOSFinalArbiter


class TestArbiterFailClosed(unittest.TestCase):
    def setUp(self):
        self.arbiter = UMIOSFinalArbiter(object())
        self.prediction = {
            "state": "QUALIFIED_PREDICTION",
            "selection": {"market": "1X2", "selection": "HOME", "odds": 2.0, "model_probability": 0.6},
        }

    def test_no_bet_qualification_never_reaches_final_qualified(self):
        result = self.arbiter.decide({}, {}, {
            "state": "NO_BET", "checks": {}, "blockers": ["MISSING_OR_INVALID:lineups"]
        }, self.prediction)
        self.assertEqual(result["state"], "NO_BET")
        self.assertEqual(result["reason"], "qualification_gate_blocked")

    def test_qualified_label_with_blockers_is_rejected(self):
        result = self.arbiter.decide({}, {}, {
            "state": "QUALIFIED", "checks": {"event": True}, "blockers": ["FIXTURE_VERIFICATION_MISSING"]
        }, self.prediction)
        self.assertEqual(result["state"], "NO_BET")
        self.assertEqual(result["reason"], "qualification_gate_blocked")

    def test_partial_true_checks_do_not_qualify(self):
        result = self.arbiter.decide({}, {}, {
            "state": "QUALIFIED",
            "checks": {"freshness": True, "external_verification": True},
            "blockers": [],
        }, self.prediction)
        self.assertEqual(result["state"], "NO_BET")
        self.assertEqual(result["reason"], "qualification_gate_blocked")

    def test_missing_qualification_checks_are_rejected(self):
        result = self.arbiter.decide({}, {}, {
            "state": "QUALIFIED", "checks": {}, "blockers": []
        }, self.prediction)
        self.assertEqual(result["state"], "NO_BET")
        self.assertEqual(result["reason"], "qualification_gate_blocked")


if __name__ == "__main__":
    unittest.main()
