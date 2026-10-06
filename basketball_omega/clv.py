"""Strict closing-line evidence contract.

CLV is UNKNOWN unless both entry and closing prices are timestamped and the
closing observation is verified to precede tip. Missing CLV is never encoded
as zero.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class CLVEvidence:
    status: str
    samples: int
    mean_clv: float | None
    source: str

def verify_clv(rows, source="unknown", min_samples=250):
    valid=[]
    for r in rows:
        if getattr(r,"entry_spread",None) is None or getattr(r,"closing_spread",None) is None:
            continue
        close_ts=getattr(r,"closing_at",None)
        cutoff=getattr(r,"cutoff_at",None)
        if close_ts is None or cutoff is None or close_ts <= cutoff:
            valid.append(float(r.entry_spread)-float(r.closing_spread))
    if len(valid) < int(min_samples):
        return CLVEvidence("UNVERIFIED",len(valid),None,source)
    return CLVEvidence("VERIFIED",len(valid),sum(valid)/len(valid),source)
