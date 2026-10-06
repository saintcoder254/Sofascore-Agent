from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class ModelWeight:
    name:str
    skill:float
    calibration:float
    independence:float
    regime:float
    weight:float

class IndependenceWeightLearner:
    """Weights models by OOS skill while penalizing correlated errors."""
    def fit(self, predictions):
        # predictions: [{name,prob,outcome,regime}, ...]
        by={}
        for r in predictions: by.setdefault(str(r["name"]),[]).append(r)
        names=sorted(by)
        metrics={}
        for n in names:
            rows=by[n]
            b=sum((float(x["prob"])-int(x["outcome"]))**2 for x in rows)/max(1,len(rows))
            skill=max(0.0,1.0-4.0*b)
            cal=max(0.05,1.0-abs(b-0.20)*3)
            metrics[n]=(skill,cal)
        errors={}
        for a in names:
            for b in names:
                if a>=b: continue
                xa=[float(x["prob"])-int(x["outcome"]) for x in by[a]]
                xb=[float(x["prob"])-int(x["outcome"]) for x in by[b]]
                m=min(len(xa),len(xb))
                if m<2: corr=0.0
                else:
                    xa=xa[:m]; xb=xb[:m]; ma=sum(xa)/m; mb=sum(xb)/m
                    va=sum((x-ma)**2 for x in xa); vb=sum((x-mb)**2 for x in xb)
                    corr=sum((x-ma)*(y-mb) for x,y in zip(xa,xb))/max(1e-9,sqrt(va*vb))
                errors[(a,b)]=max(-1,min(1,corr))
        out=[]
        raw={}
        for n in names:
            corr=max([errors.get(tuple(sorted((n,m))),0.0) for m in names if m!=n] or [0.0])
            indep=max(0.05,1.0-abs(corr))
            skill,cal=metrics[n]; score=max(0.01,skill*cal*indep)
            raw[n]=score
        total=sum(raw.values()) or 1.0
        for n in names:
            skill,cal=metrics[n]
            corr=max([errors.get(tuple(sorted((n,m))),0.0) for m in names if m!=n] or [0.0])
            out.append(ModelWeight(n,skill,cal,max(.05,1-abs(corr)),1.0,raw[n]/total))
        return out
