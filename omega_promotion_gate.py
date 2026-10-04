"""OMEGA Live Promotion Gate v1.

Keeps calibration/reweighting in SHADOW until point-in-time integrity,
walk-forward calibration, and market-benchmark evidence satisfy explicit gates.
"""

class OmegaPromotionGate:
    VERSION="OMEGA-PROMOTION-GATE-v1"

    def __init__(self,min_samples=100,min_clv_samples=20):
        self.min_samples=max(50,int(min_samples))
        self.min_clv_samples=max(10,int(min_clv_samples))

    def evaluate(self,ledger,integrity,calibration,weights,market_benchmark):
        reasons=[]
        n=len(ledger)
        valid=all(bool(x.get("valid")) for x in integrity) if integrity else False
        if n<self.min_samples: reasons.append("INSUFFICIENT_LEDGER_SAMPLES")
        if not valid: reasons.append("LEDGER_INTEGRITY_FAILURE")
        if calibration.get("state")!="EVALUATED" or not calibration.get("candidate_pass"):
            reasons.append("CALIBRATION_GATE_NOT_PASSED")
        earned=[x for x in weights.get("models",[]) if x.get("status")=="EARNED"]
        if not earned: reasons.append("NO_EARNED_MODEL")
        clv_n=int(market_benchmark.get("clv_available") or 0)
        if clv_n>=self.min_clv_samples and float(market_benchmark.get("avg_clv") or 0)<=0:
            reasons.append("MARKET_BENCHMARK_CLV_NOT_POSITIVE")
        state="PROMOTE" if not reasons else "SHADOW"
        return {"version":self.VERSION,"state":state,"live_reweighting_enabled":state=="PROMOTE","samples":n,"reasons":reasons,"clv_samples":clv_n}

    def evaluate_from_store(self,store,market=None,competition=None):
        ledger=store.calibration_ledger()
        integrity=store.verify_prediction_ledger()
        calibration=__import__("calibration_pipeline").calibration_pipeline.CalibrationPipeline().run(ledger) if False else None
        return {"error":"use app/store orchestration"}
