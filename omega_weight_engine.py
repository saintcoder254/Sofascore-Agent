"""OMEGA Evidence-Earned Weight Engine v1."""
from calibration_engine import CalibrationEngine

class OmegaWeightEngine:
    VERSION="OMEGA-WEIGHTS-v1"
    def __init__(self,min_samples=50,shrinkage=0.35):
        self.min_samples=max(20,int(min_samples)); self.shrinkage=min(.9,max(0.,float(shrinkage))); self.cal=CalibrationEngine()
    def evaluate(self,ledger,market=None,competition=None):
        rows=[r for r in ledger if (market is None or str(r.get("market"))==str(market)) and (competition is None or str(r.get("competition"))==str(competition))]
        out=[]
        for model in sorted({str(r.get("model") or "unknown") for r in rows}):
            rs=[r for r in rows if str(r.get("model") or "unknown")==model]; metrics=self.cal.evaluate(rs); n=len(rs)
            if n<self.min_samples: weight=1.; status="SHADOW"
            else:
                loss=metrics.get("log_loss"); score=1./(1.+max(0.,float(loss or 1.))); weight=(1-self.shrinkage)*score+self.shrinkage; status="EARNED"
            out.append({"model":model,"samples":n,"weight":round(weight,6),"status":status,"metrics":metrics})
        total=sum(x["weight"] for x in out if x["status"]=="EARNED")
        if total:
            for x in out:
                if x["status"]=="EARNED": x["normalized_weight"]=round(x["weight"]/total,6)
        return {"version":self.VERSION,"minimum_samples":self.min_samples,"market":market,"competition":competition,"models":out}
    def choose(self,ledger,market=None,competition=None):
        earned=[x for x in self.evaluate(ledger,market,competition)["models"] if x["status"]=="EARNED"]
        return max(earned,key=lambda x:x["normalized_weight"]) if earned else None
