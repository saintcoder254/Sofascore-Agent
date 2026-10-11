from dataclasses import dataclass
from math import erf,sqrt

@dataclass(frozen=True)
class SpecializedMarket:
    market:str
    probability:float
    fair_value:float
    uncertainty:float
    status:str

def _normal_tail(mean,sd,line):
    return .5*(1-erf((float(line)-float(mean))/(max(1e-6,float(sd))*sqrt(2))))

class MoneylineEngine:
    def predict(self,win_probability,uncertainty=0.0):
        return SpecializedMarket("moneyline",float(win_probability),float(win_probability),float(uncertainty),"READY")

class SpreadEngine:
    def predict(self,margin_mean,margin_sd,line):
        p=_normal_tail(margin_mean,margin_sd,-float(line))
        return SpecializedMarket("spread",p,float(margin_mean),float(margin_sd),"READY")

class TotalEngine:
    def predict(self,total_mean,total_sd,line):
        p=_normal_tail(total_mean,total_sd,line)
        return SpecializedMarket("total",p,float(total_mean),float(total_sd),"READY")

class HalfEngine:
    def predict(self,full_margin,full_total,sd,market="1H"):
        scale=.5 if market=="1H" else .25
        return SpecializedMarket(market,.5+.5*max(-1,min(1,full_margin/(max(sd,1)*4))),
                                 full_total*scale,sd*sqrt(scale),"MODELLED")

class TeamTotalEngine:
    def predict(self,team_mean,team_sd,line,team):
        return SpecializedMarket(f"{team}_team_total",_normal_tail(team_mean,team_sd,line),team_mean,team_sd,"READY")

class PlayerPropEngine:
    def predict(self,player,mean,sd,line):
        return SpecializedMarket(f"{player}_prop",_normal_tail(mean,sd,line),mean,sd,"READY")

class MarketSpecificEngines:
    def __init__(self):
        self.moneyline=MoneylineEngine(); self.spread=SpreadEngine(); self.total=TotalEngine()
        self.half=HalfEngine(); self.team_total=TeamTotalEngine(); self.player_prop=PlayerPropEngine()

    def run(self,state):
        out={}
        d=state["distribution"]
        out["moneyline"]=self.moneyline.predict(d["home_win_probability"],d["margin_sd"])
        if state.get("spread") is not None: out["spread"]=self.spread.predict(d["margin_mean"],d["margin_sd"],state["spread"])
        if state.get("total") is not None: out["total"]=self.total.predict(d["total_mean"],d["total_sd"],state["total"])
        out["1H"]=self.half.predict(d["margin_mean"],d["total_mean"],d["margin_sd"],"1H")
        out["Q1"]=self.half.predict(d["margin_mean"],d["total_mean"],d["margin_sd"],"Q1")
        return out
