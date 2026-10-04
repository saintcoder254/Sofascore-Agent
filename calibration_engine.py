"""OMEGA Calibration and Model Health Engine v1.

Point-in-time evaluation utilities. Never rewrites historical predictions with
later information. Supports Brier, log loss, reliability bins, calibration
error, and model-level drift summaries.
"""
import math
from collections import defaultdict

class CalibrationEngine:
    VERSION="OMEGA-CALIBRATION-v1"

    @staticmethod
    def brier(rows):
        vals=[(float(r["p"]),float(r["y"])) for r in rows if r.get("p") is not None and r.get("y") is not None]
        return sum((p-y)**2 for p,y in vals)/len(vals) if vals else None

    @staticmethod
    def log_loss(rows):
        vals=[(float(r["p"]),float(r["y"])) for r in rows if r.get("p") is not None and r.get("y") is not None]
        if not vals:return None
        return sum(-y*math.log(max(1e-12,min(1-1e-12,p)))-(1-y)*math.log(max(1e-12,min(1-1e-12,p))) for p,y in vals)/len(vals)

    @staticmethod
    def reliability(rows,bins=None):
        bins=bins or [0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90,0.95,1.01]
        out=[]
        for lo,hi in zip(bins[:-1],bins[1:]):
            x=[r for r in rows if r.get("p") is not None and lo<=float(r["p"])<hi]
            if not x:continue
            actual=sum(float(r["y"]) for r in x)/len(x); pred=sum(float(r["p"]) for r in x)/len(x)
            out.append({"low":lo,"high":hi,"samples":len(x),"predicted":pred,"actual":actual,"gap":actual-pred})
        return out

    def evaluate(self,rows):
        rel=self.reliability(rows)
        ece=sum((x["samples"]/sum(r["samples"] for r in rel))*abs(x["gap"]) for x in rel) if rel else None
        return {"version":self.VERSION,"samples":len(rows),"brier":self.brier(rows),"log_loss":self.log_loss(rows),"ece":ece,"reliability":rel}

    def compare_models(self,ledger):
        groups=defaultdict(list)
        for r in ledger:
            groups[str(r.get("model") or "unknown")].append(r)
        out=[]
        for model,rows in groups.items():
            m=self.evaluate(rows); out.append({"model":model,**m})
        return sorted(out,key=lambda x:(x["log_loss"] is None,x["log_loss"] or 999))

class ModelHealthEngine:
    VERSION="OMEGA-MODEL-HEALTH-v1"
    def assess(self,metrics):
        flags=[]
        if metrics.get("ece") is not None and metrics["ece"]>0.08:flags.append("CALIBRATION_DRIFT")
        if metrics.get("brier") is not None and metrics["brier"]>0.25:flags.append("WEAK_PROBABILITY_QUALITY")
        return {"version":self.VERSION,"state":"DEGRADED" if flags else "HEALTHY","flags":flags}
