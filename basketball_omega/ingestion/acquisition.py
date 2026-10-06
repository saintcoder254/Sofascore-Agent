"""Resumable historical acquisition orchestration.

Transport is injected. The engine never trusts a downloaded payload until the
existing normalization/quality/PIT pipeline accepts it.
"""
from dataclasses import dataclass
from typing import Callable
from .contracts import SourceRecord
from .engine import BasketballIngestionEngine
from .manifest import ManifestStore

@dataclass(frozen=True)
class AcquisitionResult:
    source:str
    dataset:str
    requested:int
    acquired:int
    failed:int
    records:tuple
    errors:tuple

class HistoricalAcquisitionEngine:
    def __init__(self, fetch:Callable, engine=None, manifest=None, retries=4):
        self.fetch=fetch; self.engine=engine or BasketballIngestionEngine()
        self.manifest=manifest or ManifestStore(); self.retries=max(1,int(retries))

    def acquire(self, source, dataset, keys, captured_at):
        records=[]; errors=[]
        for key in keys:
            last=None
            for attempt in range(self.retries):
                try:
                    payload=self.fetch(source,dataset,key)
                    if payload in (None,"",[],{}): raise ValueError("empty_payload")
                    rec=SourceRecord(source=source,endpoint=dataset,record_key=str(key),
                                     observed_at=float(captured_at),payload=payload,checksum="",
                                     source_version="v1")
                    records.append(rec); last=None; break
                except Exception as exc: last=str(exc)
            if last: errors.append({"key":str(key),"error":last})
        ing=self.engine.ingest(records)
        return AcquisitionResult(source,dataset,len(keys),len(records),len(errors),tuple(ing.records),tuple(errors))
