"""Cross-source reconciliation with conservative conflict handling."""
from dataclasses import dataclass
from collections import defaultdict
from .sources import source_for
from .contracts import NormalizedRecord, IngestionIssue

@dataclass(frozen=True)
class ReconciliationResult:
    records: tuple[NormalizedRecord,...]
    issues: tuple[IngestionIssue,...]

class SourceReconciliationAgent:
    def reconcile(self, records):
        groups=defaultdict(list)
        for r in records:
            # Same entity/effective time is the canonical reconciliation key.
            group_key=(r.entity_type,r.entity_id, r.values.get("game_time") if r.entity_type=="game" else r.effective_at)
            groups[group_key].append(r)
        chosen=[]; issues=[]
        for key, rows in groups.items():
            if len(rows)==1:
                chosen.append(rows[0]); continue
            signatures=[r.values for r in rows]
            if all(v==signatures[0] for v in signatures[1:]):
                chosen.append(max(rows,key=lambda r:r.captured_at)); continue
            ranked=sorted(rows,key=lambda r:source_for(r.source).authority,reverse=True)
            top=ranked[0]
            issues.append(IngestionIssue("warning","SOURCE_CONFLICT",top.source,top.entity_id,
                "independent sources disagree; retained highest-authority evidence and flagged conflict"))
            chosen.append(top)
        return ReconciliationResult(tuple(chosen),tuple(issues))
