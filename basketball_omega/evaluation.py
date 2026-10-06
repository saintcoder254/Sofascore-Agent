"""Leakage-resistant walk-forward metrics and promotion evidence."""
from dataclasses import dataclass, asdict
import math

@dataclass(frozen=True)
class EvaluationReport:
    samples:int
    brier:float
    log_loss:float
    ece:float
    margin_mae:float
    total_mae:float
    clv_mean:float
    clv_samples:int
    calibration_bins:int
    chronological:bool

def evaluate(rows, bins=10):
    rows=list(rows)
    if not rows:
        return EvaluationReport(0,math.inf,math.inf,math.inf,math.inf,math.inf,0.0,0,0,True)
    brier=sum((r.predicted_home_prob-r.actual_home_win)**2 for r in rows)/len(rows)
    ll=-sum(r.actual_home_win*math.log(max(r.predicted_home_prob,1e-12))+(1-r.actual_home_win)*math.log(max(1-r.predicted_home_prob,1e-12)) for r in rows)/len(rows)
    mae_m=sum(abs(r.predicted_margin-r.actual_margin) for r in rows)/len(rows)
    mae_t=sum(abs(r.predicted_total-r.actual_total) for r in rows)/len(rows)
    ece=0.0
    for b in range(bins):
        lo=b/bins; hi=(b+1)/bins
        group=[r for r in rows if lo <= r.predicted_home_prob < hi or (b==bins-1 and r.predicted_home_prob==1)]
        if group:
            conf=sum(r.predicted_home_prob for r in group)/len(group)
            acc=sum(r.actual_home_win for r in group)/len(group)
            ece += len(group)/len(rows)*abs(conf-acc)
    clvs=[]
    for r in rows:
        if None in (r.entry_spread,r.closing_spread,r.cutoff_at,r.closing_at,getattr(r,"event_at",None),getattr(r,"clv_side_spread",None)):
            continue
        if not (r.cutoff_at <= r.closing_at <= r.event_at):
            continue
        if r.clv_side_spread=="home": clvs.append(r.entry_spread-r.closing_spread)
        elif r.clv_side_spread=="away": clvs.append(r.closing_spread-r.entry_spread)
    return EvaluationReport(len(rows),brier,ll,ece,mae_m,mae_t,sum(clvs)/len(clvs) if clvs else 0.0,len(clvs),bins,all(rows[i].cutoff_at<=rows[i+1].cutoff_at for i in range(len(rows)-1)))

def report_dict(report):
    return asdict(report)
