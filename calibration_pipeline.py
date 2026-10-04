"""OMEGA Walk-Forward Calibration Pipeline v1."""
from calibration_engine import CalibrationEngine

class CalibrationPipeline:
    VERSION="OMEGA-CALIBRATION-PIPELINE-v1"
    def __init__(self,min_train=50,min_test=20):
        self.min_train=max(20,int(min_train)); self.min_test=max(10,int(min_test)); self.engine=CalibrationEngine()
    def run(self,ledger):
        rows=sorted([r for r in ledger if r.get("predicted_at") is not None],key=lambda r:r["predicted_at"])
        minimum=self.min_train+self.min_test
        if len(rows)<minimum:return {"version":self.VERSION,"state":"SHADOW","samples":len(rows),"minimum":minimum,"live_adjustment":False}
        split=max(self.min_train,int(len(rows)*.70)); train,test=rows[:split],rows[split:]
        if len(test)<self.min_test:return {"version":self.VERSION,"state":"SHADOW","samples":len(rows),"minimum":minimum,"live_adjustment":False}
        mapping={}
        for lo,hi in zip([.50,.60,.70,.80,.90],[.60,.70,.80,.90,1.01]):
            rs=[r for r in train if lo<=float(r["p"])<hi]
            if len(rs)>=10:mapping[(lo,hi)]=sum(float(r["y"]) for r in rs)/len(rs)
        raw=self.engine.evaluate(test); calibrated=[]
        for r in test:
            p=float(r["p"]); q=p
            for (lo,hi),rate in mapping.items():
                if lo<=p<hi:q=.7*p+.3*rate; break
            calibrated.append({"p":q,"y":r["y"]})
        cand=self.engine.evaluate(calibrated); passed=bool(cand["brier"] is not None and raw["brier"] is not None and cand["brier"]<raw["brier"] and cand["log_loss"]<=raw["log_loss"])
        return {"version":self.VERSION,"state":"EVALUATED","samples":len(rows),"train_samples":len(train),"test_samples":len(test),"baseline":raw,"candidate":cand,"mapping_bins":len(mapping),"candidate_pass":passed,"live_adjustment":False}
