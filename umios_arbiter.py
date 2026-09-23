import math, time

class UMIOSAdversarialLayer:
    """Challenges candidate predictions before final persistence."""
    def __init__(self,min_sources=2):
        self.min_sources=max(2,int(min_sources or 2))

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    def evaluate(self,prediction,evidence,gate):
        blockers=[]; warnings=[]
        if gate.get("state")!="QUALIFIED": blockers.append("QUALIFICATION_BLOCKED")
        if gate.get("freshness_age_seconds") is None or gate.get("freshness_age_seconds",999999)>180: blockers.append("STALE_EVIDENCE")
        if gate.get("checks",{}).get("external_verification") is not True: blockers.append("EXTERNAL_VERIFICATION_MISSING")
        event=evidence.get("event") or {}
        status=((event.get("status") or {}).get("type") or {}).get("state")
        if str(status or "").lower() in {"finished","completed","final","cancelled","postponed","abandoned","suspended"}: blockers.append("MATCH_STATE_INVALID")
        verification=evidence.get("verification") or {}
        if verification.get("conflict") or evidence.get("verification_conflicts"): blockers.append("SOURCE_CONFLICT")
        sel=prediction.get("selection") or {}
        edge=self._num(sel.get("edge")) or 0
        ev=self._num(sel.get("expected_value")) or 0
        p=self._num(sel.get("model_probability"))
        if p is None: blockers.append("MODEL_PROBABILITY_MISSING")
        if edge>0.20 or ev>0.35: blockers.append("SUSPICIOUS_EDGE")
        if p is not None and (p<0.55 or p>0.97): warnings.append("EXTREME_PROBABILITY")
        hist=prediction.get("history") or {}
        sample=min(int(hist.get("home_games") or 0),int(hist.get("away_games") or 0))
        if sample<5: blockers.append("THIN_HISTORY")
        # Independent model and market should not be wildly disconnected without a specific reason.
        if edge>0.15:warnings.append("LARGE_MODEL_MARKET_DIVERGENCE")
        return {"state":"PASS" if not blockers else "BLOCK","blockers":blockers,"warnings":warnings,
                "sample":sample,"edge":edge,"expected_value":ev,"generated_at":time.time()}

class UMIOSCalibrationLayer:
    """Conservative empirical calibration from settled UMIOS predictions."""
    def __init__(self,store,min_samples=20):
        self.store=store; self.min_samples=max(20,int(min_samples))

    def calibrate(self,p):
        rows=[r for r in self.store.predictions_with_outcomes() if str(r.get("model_version","")).startswith("UMIOS-TITAN")]
        if len(rows)<self.min_samples:return {"probability":p,"adjusted":False,"samples":len(rows)}
        bins=[]
        for lo in (0.5,0.6,0.7,0.8,0.9):
            hi=lo+0.1
            rs=[r for r in rows if lo<=r["predicted_probability"]<hi]
            if len(rs)>=self.min_samples:
                bins.append((lo,hi,sum(r["outcome"] for r in rs)/len(rs),len(rs)))
        for lo,hi,emp,n in bins:
            if lo<=p<hi:
                # Blend empirical frequency 30% with current model 70% to avoid overcorrection.
                return {"probability":round(0.7*p+0.3*emp,6),"adjusted":True,"samples":n,"empirical_rate":round(emp,6),"bin":[lo,hi]}
        return {"probability":p,"adjusted":False,"samples":len(rows)}

class UMIOSConsensusLayer:
    """Combines independent model, challenger observations, and reliability without letting a challenger override truth."""
    def __init__(self,store):
        self.store=store

    def challenger_signal(self,event,prediction):
        home=(event.get("homeTeam") or {}).get("name","").lower()
        away=(event.get("awayTeam") or {}).get("name","").lower()
        matches=[]
        for row in self.store.external_pending():
            if row["source"]!="scores24":continue
            if row["home"].lower()==home and row["away"].lower()==away:
                matches.append(row)
        return {"available":bool(matches),"matches":len(matches),"agreement":None}

    def evaluate(self,event,prediction):
        sel=prediction.get("selection") or {}
        p=sel.get("model_probability")
        if p is None:return {"state":"NO_BET","reason":"missing_model_probability"}
        calibration=UMIOSCalibrationLayer(self.store).calibrate(float(p))
        cp=calibration["probability"]
        # Challenger is informational: it can flag disagreement, but cannot manufacture a bet.
        return {"state":"PASS","raw_probability":p,"calibrated_probability":cp,"calibration":calibration}

class UMIOSFinalArbiter:
    """Final deterministic decision gate for a candidate prediction."""
    def __init__(self,store):
        self.adversarial=UMIOSAdversarialLayer()
        self.consensus=UMIOSConsensusLayer(store)

    def decide(self,event,evidence,gate,prediction):
        if prediction.get("state")!="QUALIFIED_PREDICTION":
            return {"state":"NO_BET","reason":"probability_engine_rejected","prediction":prediction}
        challenge=self.adversarial.evaluate(prediction,evidence,gate)
        consensus=self.consensus.evaluate(event,prediction)
        if challenge["state"]!="PASS" or consensus["state"]!="PASS":
            return {"state":"NO_BET","reason":"arbiter_blocked","challenge":challenge,"consensus":consensus,"prediction":prediction}
        return {"state":"FINAL_QUALIFIED","challenge":challenge,"consensus":consensus,"prediction":prediction}
