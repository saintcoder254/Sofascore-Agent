"""Adversarial data-quality gates for basketball ingestion."""
from collections import defaultdict
from .contracts import IngestionIssue

class IngestionQualityAgent:
    def validate(self, records):
        issues=[]
        seen=set()
        for r in records:
            key=(r.entity_type,r.entity_id,r.effective_at)
            if key in seen:
                issues.append(IngestionIssue("warning","DUPLICATE_RECORD",r.source,r.entity_id,"duplicate canonical observation"))
            seen.add(key)
            if r.effective_at > r.captured_at:
                issues.append(IngestionIssue("error","TIME_TRAVEL",r.source,r.entity_id,"effective time after capture"))
            v=dict(r.values or {})
            if r.entity_type=="game":
                if str(v.get("home_team_id","")) == str(v.get("away_team_id","")):
                    issues.append(IngestionIssue("error","TEAM_IDENTITY",r.source,r.game_id,"home and away team identical"))
                try:
                    if float(v.get("home_score",0) or 0)<0 or float(v.get("away_score",0) or 0)<0:
                        issues.append(IngestionIssue("error","NEGATIVE_SCORE",r.source,r.game_id,"negative score"))
                except (TypeError,ValueError):
                    issues.append(IngestionIssue("error","INVALID_SCORE",r.source,r.game_id,"score is not numeric"))
            if r.entity_type=="player":
                try:
                    minutes=float(v.get("minutes",0) or 0)
                    if minutes<0:
                        issues.append(IngestionIssue("error","NEGATIVE_MINUTES",r.source,r.entity_id,"negative minutes"))
                except (TypeError,ValueError):
                    issues.append(IngestionIssue("error","INVALID_MINUTES",r.source,r.entity_id,"minutes is not numeric"))
        return issues

    def pass_gate(self, records):
        issues=self.validate(records)
        return not any(x.severity=="error" for x in issues), issues
