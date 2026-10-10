import unittest

from fixture_audit import build_fixture_audit


class FixtureAuditTests(unittest.TestCase):
    def base(self):
        return build_fixture_audit(
            "evt-1",
            {"event": {"id": "evt-1", "homeTeam": {"name": "Quilmes AC"},
                       "awayTeam": {"name": "Agropecuario"}, "startTimestamp": 1_800_000_000},
             "data_trust": {"state": "QUARANTINED", "hard_blocks": ["CONSENSUS_BLOCK"]},
             "odds": {}},
            {"state": "NO_BET", "checks": {"fixture_identity": True},
             "blockers": ["NO_RELIABLE_MARKET_DATA"]},
            {"state": "NO_BET"},
            {"state": "NO_BET"},
            {"state": "NO_BET", "reason": "qualification_blocked"},
            generated_at=1_800_000_010,
        )

    def test_missing_trust_and_odds_are_not_promoted(self):
        audit = self.base()
        self.assertFalse(audit["source_trust"]["verified"])
        self.assertEqual(audit["market_odds"]["status"], "NOT_VERIFIED")
        self.assertEqual(audit["probability_model"]["status"], "UNAVAILABLE")
        self.assertEqual(audit["analysis"]["final_verdict"], "NO_BET")
        self.assertTrue(audit["artifact_sha256"])

    def test_fixture_identity_is_recorded(self):
        audit = self.base()
        self.assertEqual(audit["fixture"]["home"], "Quilmes AC")
        self.assertEqual(audit["fixture"]["away"], "Agropecuario")
        self.assertTrue(audit["fixture"]["identity_verified"])

    def test_trusted_aggregate_does_not_imply_positive_value(self):
        audit = build_fixture_audit(
            "evt-2",
            {"event": {"homeTeam": {"name": "Home"}, "awayTeam": {"name": "Away"}},
             "data_trust": {"state": "TRUSTED", "hard_blocks": [], "provenance": [
                 {"source": "espn", "retrieved_at": 1_800_000_000, "payload_hash": "a"},
                 {"source": "fotmob", "retrieved_at": 1_800_000_001, "payload_hash": "b"}]},
             "odds": {"market": {"source": "book", "retrieved_at": 1_800_000_001,
                                  "markets": [{"name": "1X2", "choices": [
                                      {"name": "Home", "decimalValue": 2.0},
                                      {"name": "Draw", "decimalValue": 3.0},
                                      {"name": "Away", "decimalValue": 4.0}]}]}}},
            {"state": "QUALIFIED", "checks": {}, "blockers": []},
            {"state": "ANALYZED"},
            {"model": "test-model", "selection": {"market": "1X2", "selection": "Home",
                                                     "model_probability": 0.6, "expected_value": 0.2}},
            {"state": "FINAL_QUALIFIED"},
            generated_at=1_800_000_002,
        )
        self.assertTrue(audit["source_trust"]["verified"])
        self.assertEqual(audit["market_odds"]["status"], "VERIFIED_FRESH")
        self.assertEqual(audit["probability_model"]["status"], "EXTERNAL_OR_UNCALIBRATED")
        self.assertEqual(audit["analysis"]["final_verdict"], "NO_BET")


if __name__ == "__main__":
    unittest.main()
