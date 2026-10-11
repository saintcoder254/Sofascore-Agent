"""Point-in-time snapshot builder with hard future-data exclusion."""
from dataclasses import dataclass
from collections import defaultdict
from .contracts import NormalizedRecord

@dataclass(frozen=True)
class PITSnapshot:
    cutoff_at: float
    records: tuple[NormalizedRecord,...]

class PITSnapshotAgent:
    def build(self, records, cutoff_at):
        eligible=[r for r in records if r.effective_at <= cutoff_at and r.captured_at <= cutoff_at]
        latest={}
        for r in sorted(eligible,key=lambda x:(x.entity_type,x.entity_id,x.effective_at,x.captured_at)):
            latest[(r.entity_type,r.entity_id,r.effective_at)]=r
        return PITSnapshot(float(cutoff_at),tuple(latest.values()))

    def assert_no_future_data(self, snapshot):
        return all(r.effective_at<=snapshot.cutoff_at and r.captured_at<=snapshot.cutoff_at for r in snapshot.records)
