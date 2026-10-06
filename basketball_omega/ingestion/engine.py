"""Robust ingestion orchestrator: archive -> normalize -> quality -> reconcile -> PIT."""
from dataclasses import dataclass
from .contracts import SourceRecord
from .normalizer import BasketballNormalizer
from .quality import IngestionQualityAgent
from .reconciler import SourceReconciliationAgent
from .pit import PITSnapshotAgent

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

    def ingest(self, raw_records):
        normalized=self.normalizer.normalize(raw_records)
        ok,qissues=self.quality.pass_gate(normalized.records)
        reconciliation=self.reconciler.reconcile(normalized.records) if ok else type("R",(),{"records":(), "issues":()})()
        issues=tuple(normalized.issues)+tuple(qissues)+tuple(reconciliation.issues)
        return IngestionResult(len(raw_records),len(reconciliation.records),len(normalized.quarantined),issues,reconciliation.records)

    def pit_snapshot(self, raw_records, cutoff_at):
        result=self.ingest(raw_records)
        snap=self.pit.build(result.records,cutoff_at)
        if not self.pit.assert_no_future_data(snap):
            raise ValueError("PIT_INTEGRITY_FAILURE")
        return snap
