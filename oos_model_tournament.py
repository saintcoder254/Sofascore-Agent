"""OMEGA Out-of-Sample Model Tournament v2.

Compares candidate probability models on a chronological holdout. The module
never promotes a model by complexity or in-sample fit. It can compare ledger
models and deterministic candidate probabilities supplied for the same frozen
test rows.
"""
from calibration_engine import CalibrationEngine

class OOSModelTournament:
    VERSION="OMEGA-OOS-TOURNAMENT-v2"

    def __init__(self,min_train=50,min_test=20):
        self.min_train=max(20,int(min_train)); self.min_test=max(10,int(min_test))
        self.cal=CalibrationEngine()

    def _metrics(self,rows):
        return self.cal.evaluate(rows)

    def run(self,models):
        names=sorted(models)
        usable={}
        for name,rows in models.items():
            ordered=sorted([r for r in rows if r.get("predicted_at") is not None],key=lambda x:x["predicted_at"])
            split=max(self.min_train,int(len(ordered)*.70))
            test=ordered[split:]
            usable[name]={"samples":len(ordered),"train_samples":len(ordered[:split]),"test_samples":len(test),
                          "metrics":self._metrics(test) if len(test)>=self.min_test else None,
                          "state":"EVALUATED" if len(test)>=self.min_test else "SHADOW"}
        ranked=sorted([(n,v) for n,v in usable.items() if v["state"]=="EVALUATED"],
                      key=lambda x:(x[1]["metrics"]["log_loss"] is None,x[1]["metrics"]["log_loss"] or 999))
        return {"version":self.VERSION,"models":usable,"ranking":[n for n,_ in ranked],
                "winner":ranked[0][0] if ranked else None,
                "promotion":"NONE_UNTIL_WALK_FORWARD_VALIDATION_AND_MARKET_BENCHMARK"}
