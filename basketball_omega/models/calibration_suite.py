from dataclasses import dataclass
from math import log

@dataclass(frozen=True)
class CalibrationReport:
    samples:int
    brier:float
    log_loss:float
    ece:float
    buckets:list

class CalibrationSuite:
    def evaluate(self, probs, outcomes, bins=10):
        pairs=list(zip(map(float,probs),map(int,outcomes)))
        if not pairs: return CalibrationReport(0,1,1,1,[])
        b=sum((p-y)**2 for p,y in pairs)/len(pairs)
        ll=-sum(y*log(max(p,1e-9))+(1-y)*log(max(1-p,1e-9)) for p,y in pairs)/len(pairs)
        buckets=[]; ece=0.0
        for i in range(bins):
            lo=i/bins; hi=(i+1)/bins
            rows=[x for x in pairs if lo <= x[0] < hi or (i==bins-1 and x[0]<=hi)]
            if not rows: continue
            conf=sum(x[0] for x in rows)/len(rows); acc=sum(x[1] for x in rows)/len(rows)
            gap=abs(conf-acc); ece+=gap*len(rows)/len(pairs)
            buckets.append({"low":lo,"high":hi,"count":len(rows),"confidence":conf,"accuracy":acc,"gap":gap})
        return CalibrationReport(len(pairs),b,ll,ece,buckets)
