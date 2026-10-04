"""OMEGA Out-of-Sample Model Tournament v3.

Chronological, paired evaluation. Models are compared only on common fixture/market
targets when multiple models exist. This prevents a model from appearing superior
because it was used on an easier subset of matches.
"""
from calibration_engine import CalibrationEngine

class OOSModelTournament:
    VERSION="OMEGA-OOS-TOURNAMENT-v3"

    def __init__(self,min_train=50,min_test=20):
        self.min_train=max(20,int(min_train)); self.min_test=max(10,int(min_test))
        self.cal=CalibrationEngine()

    @staticmethod
    def _key(row):
        return (str(row.get("fixture_id")), str(row.get("market")))

    def _ordered(self,rows):
        return sorted(
            [r for r in rows if r.get("predicted_at") is not None and r.get("fixture_id") is not None],
            key=lambda x:(float(x["predicted_at"]),self._key(x))
        )

    def run(self,models):
        prepared={name:self._ordered(rows) for name,rows in models.items()}
        keys_by_model={name:{self._key(r) for r in rows} for name,rows in prepared.items()}
        common=set.intersection(*keys_by_model.values()) if keys_by_model else set()

        usable={}
        for name,rows in prepared.items():
            paired=[r for r in rows if self._key(r) in common] if len(prepared)>1 else rows
            split=max(self.min_train,int(len(paired)*.70))
            train,test=paired[:split],paired[split:]
            usable[name]={
                "samples":len(paired),
                "train_samples":len(train),
                "test_samples":len(test),
                "paired":len(prepared)>1,
                "metrics":self.cal.evaluate(test) if len(test)>=self.min_test else None,
                "state":"EVALUATED" if len(test)>=self.min_test else "SHADOW",
            }

        ranked=sorted(
            [(n,v) for n,v in usable.items() if v["state"]=="EVALUATED"],
            key=lambda x:(x[1]["metrics"]["log_loss"] is None,x[1]["metrics"]["log_loss"] or 999)
        )
        return {
            "version":self.VERSION,
            "models":usable,
            "common_targets":len(common),
            "ranking":[n for n,_ in ranked],
            "winner":ranked[0][0] if ranked else None,
            "promotion":"NONE_UNTIL_WALK_FORWARD_VALIDATION_AND_MARKET_BENCHMARK",
        }
