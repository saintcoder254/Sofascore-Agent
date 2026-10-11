import math
from basketball_omega.contracts import AgentOpinion

class CalibrationAgent:
    name="calibration"
    def run(self,probs,results):
        if not probs or len(probs)!=len(results): return AgentOpinion(self.name,"CALIBRATION_BLOCK",0.0,risks=["No matched historical probability/outcome sample."])
        brier=sum((p-y)**2 for p,y in zip(probs,results))/len(probs); logloss=-sum(y*math.log(max(p,1e-9))+(1-y)*math.log(max(1-p,1e-9)) for p,y in zip(probs,results))/len(probs)
        conf=max(0,min(1,1-brier))
        return AgentOpinion(self.name,"CALIBRATED" if brier<.25 else "CALIBRATION_RISK",conf,rationale=["Brier score is used as a proper scoring rule; log loss penalizes overconfident errors."],evidence={"samples":len(probs),"brier":brier,"log_loss":logloss})
