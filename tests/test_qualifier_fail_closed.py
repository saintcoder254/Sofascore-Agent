import time
import unittest
from umios_qualifier import UMIOSQualifier

class TestQualifierFailClosed(unittest.TestCase):
    def setUp(self):
        self.q = UMIOSQualifier(stale_after=180)
        now = time.time()
        self.evidence = {
            "retrieved_at": now,
            "event": {"homeTeam":{"name":"Genoa"},"awayTeam":{"name":"Fiorentina"},
                      "status":{"type":{"state":"notstarted"}}},
            "lineups": {"home":{"players":[]},"away":{"players":[]}},
            "statistics": {"statistics": []},
            "incidents": {"incidents": []},
            "odds": {"1":{"markets":[{"choices":[{"name":"1","decimalValue":2.5}]}]}},
            "verification": {"events":[{"source":"futbol24"}]},
            "data_trust": {"state":"TRUSTED","hard_blocks":[]},
        }

    def test_untrusted_data_never_qualifies(self):
        self.evidence["data_trust"] = {"state":"QUARANTINED","hard_blocks":["CONSENSUS_BLOCK"]}
        result = self.q.qualify("fixture-1", self.evidence)
        self.assertEqual(result["state"], "NO_BET")
        self.assertTrue(any(x.startswith("DATA_TRUST_NOT_TRUSTED") for x in result["blockers"]))

    def test_missing_trust_envelope_never_qualifies(self):
        self.evidence.pop("data_trust")
        result = self.q.qualify("fixture-1", self.evidence)
        self.assertEqual(result["state"], "NO_BET")
        self.assertFalse(result["checks"]["trusted_evidence"])

    def test_invalid_timestamp_returns_blocker_not_exception(self):
        self.evidence["retrieved_at"] = "not-a-timestamp"
        result = self.q.qualify("fixture-1", self.evidence)
        self.assertEqual(result["state"], "NO_BET")
        self.assertIn("STALE_OR_INVALID_TIMESTAMP", result["blockers"])

    def test_invalid_odds_are_not_counted_as_market_evidence(self):
        self.evidence["odds"] = {"1":{"markets":[{"choices":[{"name":"1","decimalValue":"nan"}]}]}}
        result = self.q.qualify("fixture-1", self.evidence)
        self.assertEqual(result["state"], "NO_BET")
        self.assertIn("NO_RELIABLE_MARKET_DATA", result["blockers"])

if __name__ == "__main__":
    unittest.main()
