"""OMEGA Model Tournament v1.

Ranks models by out-of-sample probability quality rather than assigning permanent
weights by intuition. A model must earn weight through historical performance.
"""
from calibration_engine import CalibrationEngine

class ModelTournament:
    VERSION="OMEGA-MODEL-TOURNAMENT-v1"
    def __init__(self): self.cal=CalibrationEngine()
    def rank(self,ledger):
        results=self.cal.compare_models(ledger)
        return {"version":self.VERSION,"ranking":results,
                "rule":"Use performance only from point-in-time settled predictions; require sufficient samples before changing live weights."}
