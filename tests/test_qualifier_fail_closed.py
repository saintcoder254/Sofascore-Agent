import copy
import time
import unittest

from umios_qualifier import UMIOSQualifier


class TestQualifierFailClosed(unittest.TestCase):
    def setUp(self):
        self.q = UMIOSQualifier(stale_after=180)
        self.now = time.time()
        kickoff = self.now + 3600
        self.event = {
            "startTimestamp": kickoff,
            "homeTeam": {"name": "Genoa", "id": 1},
            "awayTeam": {"name": "Fiorentina", "id": 2},
            "tournament": {"name": "Serie A"},
            "status": {"type": {"state": "notstarted"}},
        }
        self.evidence = {
            "retrieved_at": self.now,
            "event": copy.deepcopy(self.event),
            "lineups": {
                "home": {"players": [{"player": {"id": 11, "name": "Home Player"}}]},
                "away": {"players": [{"player": {"id": 22, "name": "Away Player"}}]},
            },
            "statistics": {"statistics": [{"groups": [{"statisticsItems": [
                {"name": "Ball possession", "home": "51%", "away": "49%"}
            ]}]}]},
            "incidents": {"incidents": []},
            "odds": {"1": {"markets": [{"choices": [{"name": "Home", "decimalValue": 2.5}]}]}},
            "verification": {"source": "futbol24", "events": []},
            "final_results": {"sources": [
                {"source": "espn", "events": [{
                    "startTimestamp": kickoff, "homeTeam": {"name": "Genoa"},
                    "awayTeam": {"name": "Fiorentina"}, "competition": {"name": "Italian Serie A"}
                }]},
                {"source": "fotmob", "events": [{
                    "startTimestamp": kickoff, "homeTeam": {"name": "Genoa"},
                    "awayTeam": {"name": "Fiorentina"}, "tournament": {"name": "Serie A"}
                }]},
            ]},
            "verification_diagnostics": {
                "required_independent_sources": 2,
                "matched_fixture_sources": ["espn", "fotmob"],
                "matched_fixture_source_count": 2,
            },
            "data_trust": {
                "state": "TRUSTED", "hard_blocks": [],
                "consensus": {"state": "PASS", "available_sources": ["sofascore", "espn", "fotmob"]},
            },
        }

    def test_complete_fixture_evidence_can_qualify(self):
        result = self.q.qualify("fixture-1", self.evidence, now=self.now)
        self.assertEqual(result["state"], "QUALIFIED", result["blockers"])

    def test_empty_required_sections_never_pass(self):
        for key in ("event", "lineups", "statistics", "incidents"):
            with self.subTest(section=key):
                evidence = copy.deepcopy(self.evidence)
                evidence[key] = {}
                result = self.q.qualify("fixture-1", evidence, now=self.now)
                self.assertEqual(result["state"], "NO_BET")
                self.assertFalse(result["checks"][key])

    def test_empty_lineups_and_statistics_are_not_substantive(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["lineups"] = {"home": {"players": []}, "away": {"players": []}}
        evidence["statistics"] = {"statistics": []}
        result = self.q.qualify("fixture-1", evidence, now=self.now)
        self.assertEqual(result["state"], "NO_BET")
        self.assertFalse(result["checks"]["lineups"])
        self.assertFalse(result["checks"]["statistics"])

    def test_unknown_status_fails_closed(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["event"]["status"]["type"]["state"] = "unknown"
        result = self.q.qualify("fixture-1", evidence, now=self.now)
        self.assertEqual(result["state"], "NO_BET")
        self.assertIn("MATCH_STATE_UNKNOWN_OR_INELIGIBLE", result["blockers"])

    def test_live_and_terminal_states_fail_closed(self):
        # Only explicit pre-match states may proceed to probability analysis.
        for state in (
            "inprogress", "in_progress", "live", "1sthalf", "2ndhalf",
            "halftime", "paused", "finished", "completed", "final",
            "post", "cancelled", "postponed", "abandoned", "suspended", "",
        ):
            with self.subTest(state=state):
                evidence = copy.deepcopy(self.evidence)
                evidence["event"]["status"]["type"]["state"] = state
                result = self.q.qualify("fixture-1", evidence, now=self.now)
                self.assertEqual(result["state"], "NO_BET")
                self.assertFalse(result["checks"]["pre_match_state"])
                self.assertIn("MATCH_STATE_UNKNOWN_OR_INELIGIBLE", result["blockers"])

    def test_explicit_pre_match_states_are_allowlisted(self):
        for state in ("notstarted", "not_started", "not started", "scheduled", "upcoming", "created"):
            with self.subTest(state=state):
                evidence = copy.deepcopy(self.evidence)
                evidence["event"]["status"]["type"]["state"] = state
                result = self.q.qualify("fixture-1", evidence, now=self.now)
                self.assertTrue(result["checks"]["pre_match_state"])

    def test_unrelated_verification_events_do_not_count(self):
        evidence = copy.deepcopy(self.evidence)
        for source in evidence["final_results"]["sources"]:
            source["events"][0]["homeTeam"]["name"] = "Roma"
            source["events"][0]["awayTeam"]["name"] = "Lazio"
        result = self.q.qualify("fixture-1", evidence, now=self.now)
        self.assertEqual(result["state"], "NO_BET")
        self.assertFalse(result["checks"]["external_verification"])

    def test_one_independent_matching_source_is_insufficient(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["final_results"]["sources"] = evidence["final_results"]["sources"][:1]
        evidence["verification_diagnostics"]["matched_fixture_sources"] = ["espn"]
        evidence["verification_diagnostics"]["matched_fixture_source_count"] = 1
        result = self.q.qualify("fixture-1", evidence, now=self.now)
        self.assertEqual(result["state"], "NO_BET")
        self.assertFalse(result["checks"]["external_verification"])

    def test_future_timestamp_fails_closed(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["retrieved_at"] = self.now + 600
        result = self.q.qualify("fixture-1", evidence, now=self.now)
        self.assertEqual(result["state"], "NO_BET")
        self.assertFalse(result["checks"]["freshness"])

    def test_malformed_odds_payload_does_not_raise_or_qualify(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["odds"] = {"1": {"markets": "not-a-list"}}
        result = self.q.qualify("fixture-1", evidence, now=self.now)
        self.assertEqual(result["state"], "NO_BET")
        self.assertFalse(result["checks"]["market_data"])


if __name__ == "__main__":
    unittest.main()
