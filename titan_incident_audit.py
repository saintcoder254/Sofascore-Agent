"""Post-incident audit and counterfactual diagnostics for UMIOS TITAN."""
from __future__ import annotations
import time
class TitanIncidentAudit:
    VERSION="EMM-INCIDENT-AUDIT-v1.0"
    def audit_prediction(self,row):
        f=row.get("features") or {}; outcome=row.get("outcome"); p=float(row.get("predicted_probability") or 0)
        return {"prediction_id":row.get("prediction_id"),"fixture_id":row.get("fixture_id"),"market":row.get("market"),
                "selection":row.get("selection"),"probability":p,"outcome":outcome,
                "error":None if outcome is None else round(p-float(outcome),4),
                "overconfidence":bool(outcome==0 and p>=0.70),"features":f,"generated_at":time.time()}
    def audit(self,store,limit=200):
        rows=store.predictions_with_outcomes()[-int(limit):]; audits=[self.audit_prediction(r) for r in rows]
        losses=[x for x in audits if x["outcome"]==0]
        return {"version":self.VERSION,"samples":len(audits),"losses":len(losses),
                "overconfident_losses":sum(x["overconfidence"] for x in losses),
                "by_market":self._group(losses),"audits":audits}
    @staticmethod
    def _group(rows):
        out={}
        for r in rows:
            b=out.setdefault(r["market"],{"losses":0,"overconfident":0});b["losses"]+=1;b["overconfident"]+=int(r["overconfidence"])
        return out
    def counterfactual_basketball(self,guard_result):
        return {"would_have_blocked":guard_result.state=="BLOCK","guard_state":guard_result.state,
                "reason":guard_result.blockers or guard_result.warnings}