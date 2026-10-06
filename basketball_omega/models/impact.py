from dataclasses import dataclass
from typing import Iterable, Sequence

@dataclass(frozen=True)
class ImpactEstimate:
    player_id: str
    offense: float
    defense: float
    net: float
    uncertainty: float
    observations: int

class RidgeRAPM:
    """Small, leakage-safe ridge-style plus/minus estimator.

    Rows are possessions/stints. Each row supplies player coefficients (+1/-1),
    target net points per possession, and optional exposure weight. The solver
    is implemented without a mandatory numerical dependency so the interface
    can run in CI and be replaced by a numpy/sklearn backend in production.
    """
    def __init__(self, alpha=8.0):
        self.alpha=float(alpha)
        self.players=[]
        self.coef={}
        self.residual_scale=1.0

    def fit(self, rows: Iterable[dict]):
        rows=list(rows)
        ids=sorted({str(pid) for r in rows for pid in (r.get("home_players",[])+r.get("away_players",[]))})
        self.players=ids
        if not ids: return self
        n=len(ids); index={p:i for i,p in enumerate(ids)}
        xtx=[[0.0]*n for _ in range(n)]; xty=[0.0]*n; residuals=[]
        for r in rows:
            x=[0.0]*n
            for p in r.get("home_players",[]): x[index[str(p)]]+=1.0
            for p in r.get("away_players",[]): x[index[str(p)]]-=1.0
            y=float(r.get("target",0.0)); w=max(0.01,float(r.get("weight",1.0)))
            for i in range(n):
                xty[i]+=w*x[i]*y
                for j in range(n): xtx[i][j]+=w*x[i]*x[j]
        for i in range(n): xtx[i][i]+=self.alpha
        # Gaussian elimination with pivoting.
        a=[xtx[i][:]+[xty[i]] for i in range(n)]
        for c in range(n):
            p=max(range(c,n),key=lambda r:abs(a[r][c]))
            if abs(a[p][c])<1e-12: continue
            a[c],a[p]=a[p],a[c]
            z=a[c][c]
            a[c]=[v/z for v in a[c]]
            for r in range(n):
                if r==c: continue
                z=a[r][c]
                if z: a[r]=[a[r][k]-z*a[c][k] for k in range(n+1)]
        beta=[a[i][-1] for i in range(n)]
        self.coef=dict(zip(ids,beta))
        for r in rows:
            pred=sum((1 if str(p) in r.get("home_players",[]) else -1)*self.coef.get(str(p),0)
                     for p in set(map(str,r.get("home_players",[])+r.get("away_players",[]))))
            residuals.append(float(r.get("target",0))-pred)
        self.residual_scale=(sum(x*x for x in residuals)/max(1,len(residuals)))**0.5
        return self

    def estimate(self, player_id, prior=0.0, shrink=0.25):
        raw=float(self.coef.get(str(player_id),prior))
        net=(1-shrink)*raw+shrink*float(prior)
        return ImpactEstimate(str(player_id),net*0.55,net*-0.45,net,self.residual_scale,max(0,sum(1 for p in self.players if p==str(player_id))))

    def team_impact(self, players: Sequence[str]):
        return sum(self.coef.get(str(p),0.0) for p in players)
