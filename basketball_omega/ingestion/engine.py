"""Robust ingestion orchestrator: normalize -> quality -> reconcile -> PIT."""
from dataclasses import dataclass
from .normalizer import BasketballNormalizer
from .quality import IngestionQualityAgent
from .reconciler import SourceReconciliationAgent
from .pit import PITSnapshotAgent
from .contracts import IngestionIssue

@dataclass(frozen=True)
class IngestionResult:
    normalized_count:int
    accepted_count:int
    quarantined_count:int
    issues:tuple
    records:tuple

class BasketballIngestionEngine:
    def __init__(self):
        self.normalizer=BasketballNormalizer()
        self.quality=IngestionQualityAgent()
        self.reconciler=SourceReconciliationAgent()
        self.pit=PITSnapshotAgent()

    def _raw_semantic_checks(self, raw_records):
        issues=[]
        # These checks intentionally run before normalization so malformed-but-
        # identifiable evidence cannot make a quality failure disappear.
        for r in raw_records:
            v=dict(r.payload or {})
            entity=str(v.get("entity_type",""))
            if entity=="player":
                try:
                    if float(v.get("minutes",0) or 0)<0:
                        issues.append(IngestionIssue("error","NEGATIVE_MINUTES",r.source,r.record_key,"negative minutes"))
                except (TypeError,ValueError):
                    issues.append(IngestionIssue("error","INVALID_MINUTES",r.source,r.record_key,"minutes is not numeric"))
        return issues

    def ingest(self, raw_records):
        raw_records=list(raw_records)
        normalized=self.normalizer.normalize(raw_records)
        qissues=list(self._raw_semantic_checks(raw_records))
        ok, canonical_qissues=self.quality.pass_gate(normalized.records)
        qissues.extend(canonical_qissues)
        reconciliation=self.reconciler.reconcile(normalized.records)
        issues=tuple(normalized.issues)+tuple(qissues)+tuple(reconciliation.issues)
        return IngestionResult(len(raw_records),len(reconciliation.records),len(normalized.quarantined),issues,reconciliation.records)

    def pit_snapshot(self, raw_records, cutoff_at):
        result=self.ingest(raw_records)
        snap=self.pit.build(result.records,cutoff_at)
        if not self.pit.assert_no_future_data(snap):
            raise ValueError("PIT_INTEGRITY_FAILURE")
        return snap
