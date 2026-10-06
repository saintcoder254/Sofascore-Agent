"""Cross-source reconciliation with conservative conflict handling."""
from dataclasses import dataclass
from collections import defaultdict
from .sources import source_priority
from .contracts import NormalizedRecord, IngestionIssue

@dataclass(frozen=True)
class ReconciliationResult:
    records: tuple[NormalizedRecord,...]
    issues: tuple[IngestionIssue,...]

class SourceReconciliationAgent:
    def reconcile(self, records):
        groups=defaultdict(list)
        for r in records:
            groups[(r.entity_type,r.entity_id,r.effective_at)].append(r)
        chosen=[]; issues=[]
        for key, rows in groups.items():
            values=[r.values for r in rows]
            if all(v==values[0] for v in values[1:]):
                chosen.append(max(rows,key=lambda r:r.captured_at))
                continue
            ranked=sorted(rows,key=lambda r: next((s.authority for s in source_priority([r.source])),0),reverse=True)
            top=ranked[0]
            if len(ranked)>1 and ranked[0].values != ranked[1].values:
                issues.append(IngestionIssue("warning","SOURCE_CONFLICT",top.source,top.entity_id,"independent sources disagree; retained highest-authority evidence and flagged conflict"))
            chosen.append(top)
        return ReconciliationResult(tuple(chosen),tuple(issues))
