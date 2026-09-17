import time
from result_verifier import ResultVerifierAgent


class SettlementAgent:
    """Settles UMIOS and external predictions only after integrity checks."""
    def __init__(self, store):
        self.store = store
        self.verifier = ResultVerifierAgent()

    def settle_prediction(self, row, result):
        outcome = self.verifier.settle(row, result)
        if outcome is None:
            return {"status": "UNRESOLVED"}
        self.store.record_outcome(row["prediction_id"], outcome, time.time())
        return {"status": "SETTLED", "outcome": outcome}

    def settle_external(self, row, result):
        outcome = self.verifier.settle(row, result)
        if outcome is None:
            return {"status": "UNRESOLVED"}
        self.store.record_external_outcome(row["id"], outcome, time.time())
        return {"status": "SETTLED", "outcome": outcome}
