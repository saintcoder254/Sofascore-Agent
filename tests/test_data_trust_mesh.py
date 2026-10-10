import json, time, unittest
from data_trust_mesh import DataTrustMesh

def obs(source, home="A", away="B", hs=1, a=0, age=5):
    return {"source":source,"retrieved_at":time.time()-age,
            "payload":{"homeTeam":{"name":home,"score":hs},"awayTeam":{"name":away,"score":a},
                       "status":{"type":{"state":"finished"}}}}

class TestDataTrustMesh(unittest.TestCase):
    def test_trust_envelope_can_be_attached_to_observed_event_without_cycle(self):
        event = {"homeTeam": {"name": "A", "score": 1},
                 "awayTeam": {"name": "B", "score": 0},
                 "status": {"type": {"state": "finished"}}}
        other = {"homeTeam": {"name": "A", "score": 1},
                 "awayTeam": {"name": "B", "score": 0},
                 "status": {"type": {"state": "finished"}}}
        envelope = DataTrustMesh().evaluate([
            {"source": "sofascore", "retrieved_at": time.time(), "payload": event},
            {"source": "fotmob", "retrieved_at": time.time(), "payload": other},
        ])
        event["data_trust"] = envelope
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":"))
        self.assertIn('"data_trust"', encoded)
        self.assertNotIn('"payload": {"homeTeam"', encoded)

    def test_two_independent_agreeing_sources_are_trusted(self):
        out=DataTrustMesh().evaluate([obs("sofascore"),obs("fotmob")])
        self.assertEqual(out["state"],"TRUSTED")
        self.assertEqual(out["consensus"]["winner"]["result"],"HOME")
    def test_conflicting_scores_are_quarantined(self):
        out=DataTrustMesh().evaluate([obs("sofascore",hs=1,a=0),obs("fotmob",hs=2,a=1)])
        self.assertEqual(out["state"],"QUARANTINED")
        self.assertIn("CONFLICT_BLOCK",out["hard_blocks"])
    def test_single_source_cannot_claim_consensus(self):
        out=DataTrustMesh().evaluate([obs("sofascore")])
        self.assertEqual(out["state"],"QUARANTINED")
        self.assertIn("CONSENSUS_BLOCK",out["hard_blocks"])
    def test_stale_source_cannot_count_as_consensus(self):
        out=DataTrustMesh(max_age_seconds=30).evaluate([obs("sofascore",age=5),obs("fotmob",age=60)])
        self.assertEqual(out["state"],"QUARANTINED")
        self.assertIn("CONSENSUS_BLOCK",out["hard_blocks"])
    def test_stale_data_is_quarantined(self):
        out=DataTrustMesh(max_age_seconds=30).evaluate([obs("sofascore",age=60),obs("fotmob",age=60)])
        self.assertEqual(out["state"],"QUARANTINED")
        self.assertIn("FRESHNESS_BLOCK",out["hard_blocks"])

if __name__=="__main__": unittest.main()
