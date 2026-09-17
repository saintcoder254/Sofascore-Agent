import re
import time


class VerificationLearningAgent:
    """Settles UMIOS and external predictions only after independent final-result consensus."""
    def __init__(self, store, verifier, min_sources=2):
        self.store = store
        self.verifier = verifier
        self.min_sources = max(2, int(min_sources))

    @staticmethod
    def _name(value):
        value = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
        value = re.sub(r"\b(fc|cf|sc|afc|ac|club|women|w|u21|u23|ii|b)\b", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    def _matching_events(self, events, home, away):
        h, a = self._name(home), self._name(away)
        out = []
        for event in events or []:
            eh = self._name((event.get("homeTeam") or {}).get("name"))
            ea = self._name((event.get("awayTeam") or {}).get("name"))
            if eh == h and ea == a:
                out.append(event)
        return out

    def _payloads_for_fixture(self, fixture, home=None, away=None):
        payload = fixture.get("payload") or {}
        verification = payload.get("verification") or {}
        candidates = []
        final_results = verification.get("final_results") or {}
        if isinstance(final_results, dict):
            for source_payload in final_results.get("sources", []):
                if isinstance(source_payload, dict):
                    candidates.extend(source_payload.get("events", []))
        for key in ("results", "independent_results", "futbol24"):
            value = verification.get(key)
            if isinstance(value, dict): candidates.extend(value.get("events", []))
            elif isinstance(value, list): candidates.extend(value)
        if not candidates and home is None and away is None:
            candidates.append(payload)
        if home is None: return candidates
        matched = []
        for event in candidates:
            if self._name((event.get("homeTeam") or {}).get("name")) == self._name(home) and self._name((event.get("awayTeam") or {}).get("name")) == self._name(away):
                matched.append(event)
        return matched

    def _verify(self, payloads):
        consensus = self.verifier.verify_consensus(payloads, required=self.min_sources)
        return consensus if consensus.get("status") == "VERIFIED" else None

    def _settle_external(self):
        resolved = blocked = unresolved = 0
        for row in self.store.external_pending():
            fixture = self.store.find_current_fixture(row["home"], row["away"])
            if not fixture:
                unresolved += 1
                continue
            payloads = self._payloads_for_fixture(fixture, row["home"], row["away"])
            consensus = self._verify(payloads)
            if not consensus:
                unresolved += 1
                continue
            outcome = self.verifier.settle(row, consensus["result"])
            if outcome is None:
                unresolved += 1
                continue
            self.store.record_external_outcome(row["id"], outcome, time.time())
            resolved += 1
        return resolved, blocked, unresolved

    def run(self):
        resolved = blocked = unresolved = 0
        for row in self.store.pending_predictions():
            fixture = self.store.get_current(str(row["fixture_id"]))
            if not fixture:
                unresolved += 1
                continue
            payload = fixture.get("payload") or {}
            if self.store.fixture_has_conflict(payload):
                blocked += 1
                continue
            payloads = self._payloads_for_fixture(fixture)
            consensus = self._verify(payloads)
            if not consensus:
                unresolved += 1
                continue
            outcome = self.verifier.settle(row, consensus["result"])
            if outcome is None:
                unresolved += 1
                continue
            self.store.record_outcome(row["prediction_id"], outcome, time.time())
            resolved += 1
        ext_resolved, ext_blocked, ext_unresolved = self._settle_external()
        return {"resolved": resolved + ext_resolved,"external_resolved": ext_resolved,"blocked_conflicts": blocked + ext_blocked,"unresolved": unresolved + ext_unresolved,"external_unresolved": ext_unresolved,"required_sources": self.min_sources}
