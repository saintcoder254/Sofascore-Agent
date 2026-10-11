from dataclasses import dataclass

@dataclass(frozen=True)
class MarketEstimate:
    market:str
    probability:float|None
    fair_line:float|None
    edge:float|None
    uncertainty:float
    status:str

class MarketEngineSuite:
    """Independent market transformations sharing one PIT basketball distribution."""
    def moneyline(self,d): return MarketEstimate("moneyline",d.home_win_probability,None,None,d.margin_sd,"OK")
    def spread(self,d,line):
        p=d.spread_cover_probability if d.spread_cover_probability is not None else .5
        return MarketEstimate("spread",p,d.margin_mean,float(p-.5),d.margin_sd,"OK")
    def total(self,d,line):
        p=d.over_probability if d.over_probability is not None else .5
        return MarketEstimate("total",p,d.total_mean,float(p-.5),d.total_sd,"OK")
    def first_half(self,home_total,away_total,home_win_prob=.5):
        return MarketEstimate("1H",home_win_prob,None,None,max(1.0,abs(home_total-away_total)/2),"APPROX")
    def first_quarter(self,home_total,away_total,home_win_prob=.5):
        return MarketEstimate("Q1",home_win_prob,None,None,max(1.0,abs(home_total-away_total)/4),"APPROX")
    def team_total(self,team_mean,line,sd):
        from math import erf,sqrt
        p=.5*(1-erf((float(line)-team_mean)/(max(1e-6,sd)*sqrt(2))))
        return MarketEstimate("team_total",p,team_mean,p-.5,sd,"OK")
    def player_prop(self,mean,sd,line):
        from math import erf,sqrt
        p=.5*(1-erf((float(line)-mean)/(max(1e-6,sd)*sqrt(2))))
        return MarketEstimate("player_prop",p,mean,p-.5,sd,"OK")
    def all_markets(self,d,spread=None,total=None):
        return {"moneyline":self.moneyline(d),
                "spread":self.spread(d,spread) if spread is not None else None,
                "total":self.total(d,total) if total is not None else None}
