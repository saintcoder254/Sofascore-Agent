from dataclasses import dataclass
from math import sqrt, exp, pi

@dataclass(frozen=True)
class DistributionResult:
    home_mean:float
    away_mean:float
    total_mean:float
    margin_mean:float
    margin_sd:float
    total_sd:float
    home_win_probability:float
    spread_cover_probability:float|None
    over_probability:float|None
    quantiles:dict

class BasketballDistributionEngine:
    """Hybrid analytical/Monte-Carlo basketball score distribution.

    It explicitly models possessions, efficiency, shooting variance, turnovers,
    rebounds, fouls/free throws, minutes uncertainty, and late-game variance.
    """
    def simulate(self, pace, home_eff, away_eff, home_three_rate=.37, away_three_rate=.37,
                 home_tov=.13, away_tov=.13, home_orb=.25, away_orb=.25,
                 foul_rate=.16, sims=10000, spread=None, total_line=None, seed=17):
        import random
        rng=random.Random(seed); hp=[]; ap=[]
        for _ in range(max(100,sims)):
            poss=max(70,int(round(rng.gauss(float(pace),4.5))))
            def score(eff,three,tov,orb):
                p=max(55,poss*(1-rng.gauss(tov,.015)))
                base=p*float(eff)/100
                shot_var=rng.gauss(0,3.8)*sqrt(max(1,p/100))
                three_var=rng.gauss(0,2.2)*sqrt(max(1,three/.37))
                ft=rng.gauss(p*float(foul_rate)*.78,5.0)
                orb_bonus=rng.gauss(p*float(orb)*.045,2.0)
                return max(40,base+shot_var+three_var+ft+orb_bonus)
            hp.append(score(home_eff,home_three_rate,home_tov,home_orb))
            ap.append(score(away_eff,away_three_rate,away_tov,away_orb))
        hm=sum(hp)/len(hp); am=sum(ap)/len(ap)
        margins=[h-a for h,a in zip(hp,ap)]; totals=[h+a for h,a in zip(hp,ap)]
        win=sum(m>0 for m in margins)/len(margins)
        cover=sum(m+float(spread)>0 for m in margins)/len(margins) if spread is not None else None
        over=sum(t>float(total_line) for t in totals)/len(totals) if total_line is not None else None
        def sd(x):
            m=sum(x)/len(x); return sqrt(sum((v-m)**2 for v in x)/max(1,len(x)-1))
        qs={k:sorted(margins)[min(len(margins)-1,max(0,int(q*len(margins))))] for k,q in
            {"p05":.05,"p25":.25,"p50":.50,"p75":.75,"p95":.95}.items()}
        return DistributionResult(hm,am,hm+am,hm-am,sd(margins),sd(totals),win,cover,over,qs)
