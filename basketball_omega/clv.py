"""Strict, point-in-time closing-line evidence.

A CLV observation is valid only when entry and closing lines are present,
the close occurs after the model cutoff, and the close is no later than tip.
Missing or ambiguous CLV is UNKNOWN, never zero.
"""
from dataclasses import dataclass
import random

@dataclass(frozen=True)
class CLVEvidence:
    status: str
    samples: int
    mean_clv: float | None
    lower_ci: float | None
    upper_ci: float | None
    source: str
    method: str = "bootstrap_percentile"

def _side_clv(entry, close, side, market):
    side=str(side).lower()
    market=str(market).lower()
    if market == "spread":
        return entry-close if side == "home" else close-entry
    if market == "total":
        return close-entry if side == "over" else entry-close
    raise ValueError(f"unsupported_clv_market:{market}")

def _bootstrap_mean_ci(values, seed=17, resamples=1000):
    n=len(values)
    if n < 2:
        return (sum(values)/n if n else None, None, None)
    rng=random.Random(seed)
    means=[]
    for _ in range(int(resamples)):
        total=0.0
        for _ in range(n): total += values[rng.randrange(n)]
        means.append(total/n)
    means.sort()
    lo=means[max(0,int(0.025*len(means))-1)]
    hi=means[min(len(means)-1,int(0.975*len(means)))]
    return sum(values)/n,lo,hi

def verify_clv(rows, source="unknown", min_samples=250, market="spread", resamples=1000):
    valid=[]
    entry_attr="entry_spread" if market=="spread" else "entry_total"
    close_attr="closing_spread" if market=="spread" else "closing_total"
    time_attr="closing_at" if market=="spread" else "closing_total_at"
    side_attr="clv_side_spread" if market=="spread" else "clv_side_total"
    for r in rows:
        entry=getattr(r,entry_attr,None); close=getattr(r,close_attr,None)
        cutoff=getattr(r,"cutoff_at",None); close_ts=getattr(r,time_attr,None)
        event_ts=getattr(r,"event_at",None); side=getattr(r,side_attr,None)
        if None in (entry,close,cutoff,close_ts,event_ts,side): continue
        if not (float(cutoff) <= float(close_ts) <= float(event_ts)): continue
        try: valid.append(_side_clv(float(entry),float(close),str(side),market))
        except ValueError: continue
    if len(valid) < int(min_samples):
        return CLVEvidence("UNVERIFIED",len(valid),None,None,None,source)
    mean,lo,hi=_bootstrap_mean_ci(valid,resamples=resamples)
    return CLVEvidence("VERIFIED",len(valid),mean,lo,hi,source)