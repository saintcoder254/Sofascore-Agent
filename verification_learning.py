import time


class VerificationLearningAgent:
    """Resolves external and UMIOS predictions only after verified final results."""
    def __init__(self, store, verifier, min_sources=2):
        self.store = store
        self.verifier = verifier
        self.min_sources = int(min_sources)

    def _payloads_for_fixture(self, fixture):
        payload = fixture.get("payload") or {}
        candidates = [payload]
        verification = payload.get("verification") or {}
        for key in ("results", "final_results", "independent_results"):
            value = verification.get(key)
            if isinstance(value, list): candidates.extend(value)
        return candidates

    def run(self):
        resolved = blocked = unresolved = 0
        # Current cache is the primary completed result. A fixture marked conflicted is never settled.
        for row in self.store.pending_predictions():
            fixture = self.store.get_current(str(row["fixture_id"]))
            if not fixture:
                unresolved += 1; continue
            payload = fixture["payload"]
            if self.store.fixture_has_conflict(payload):
                blocked += 1; continue
            consensus = self.verifier.verify_consensus(self._payloads_for_fixture(fixture), required=self.min_sources)
            if consensus["status"] == "CONFLICT":
                blocked += 1; continue
            if consensus["status"] not in {"VERIFIED", "SINGLE_SOURCE"}:
                unresolved += 1; continue
            outcome = self.verifier.settle(row, consensus["result"])
            if outcome is None:
                unresolved += 1; continue
            self.store.record_outcome(row["prediction_id"], outcome, time.time()); resolved += 1
        return {"resolved": resolved, "blocked_conflicts": blocked, "unresolved": unresolved, "required_sources": self.min_sources}
