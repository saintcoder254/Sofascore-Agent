"""Immutable contracts for the basketball historical ingestion mesh."""
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class SourceRecord:
    source: str
    endpoint: str
    record_key: str
    observed_at: float
    payload: dict[str, Any]
    checksum: str
    source_version: str = ""

@dataclass(frozen=True)
class NormalizedRecord:
    entity_type: str
    entity_id: str
    game_id: str
    effective_at: float
    captured_at: float
    source: str
    values: dict[str, Any]
    provenance: tuple[str, ...] = ()

@dataclass(frozen=True)
class IngestionIssue:
    severity: str
    code: str
    source: str
    record_key: str
    message: str

@dataclass
class IngestionBatch:
    records: list[NormalizedRecord] = field(default_factory=list)
    issues: list[IngestionIssue] = field(default_factory=list)
    quarantined: list[SourceRecord] = field(default_factory=list)
    source_counts: dict[str,int] = field(default_factory=dict)

    @property
    def accepted(self):
        return len(self.records)
