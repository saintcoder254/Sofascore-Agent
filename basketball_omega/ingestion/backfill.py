from dataclasses import dataclass
from typing import Iterable,Callable
from .acquisition import HistoricalAcquisitionEngine
from .archive import RawEvidenceArchive

@dataclass(frozen=True)
class BackfillCheckpoint:
    source:str
    dataset:str
    key:str
    status:str
    records:int
    error:str|None=None

class HistoricalBackfill:
    """Checkpointed backfill runner; failed keys never silently disappear."""
    def __init__(self, acquisition:HistoricalAcquisitionEngine, archive:RawEvidenceArchive):
        self.acquisition=acquisition; self.archive=archive
    def run(self, source, dataset, keys:Iterable[str], captured_at:float, checkpoint:Callable[[BackfillCheckpoint],None]|None=None):
        rows=[]
        for key in keys:
            try:
                result=self.acquisition.acquire(source,dataset,[key],captured_at)
                ok=result.acquired==1 and not result.errors
                row=BackfillCheckpoint(source,dataset,str(key),"complete" if ok else "failed",len(result.records),None if ok else str(result.errors))
            except Exception as exc:
                row=BackfillCheckpoint(source,dataset,str(key),"failed",0,str(exc))
            rows.append(row)
            if checkpoint: checkpoint(row)
        return rows
