import json, time
from basketball_omega.agents.online_learner import OnlineWeightLearner

class BasketballLearningLoop:
    """Postgame learning service. Stores attribution without silently promoting models."""
    def __init__(self,state_path="basketball_omega_state.json"):
        self.state_path=state_path; self.learner=OnlineWeightLearner(); self.history=[]
    def learn(self,opinions,actual_margin,actual_total=None):
        result=self.learner.update(opinions,actual_margin); result["actual_total"]=actual_total; result["timestamp"]=time.time(); self.history.append(result); self._save(); return result
    def _save(self):
        with open(self.state_path,"w",encoding="utf-8") as f: json.dump({"weights":self.learner.weights,"samples":self.learner.samples,"history":self.history[-500:]},f,indent=2)
