import random, math
from basketball_omega.contracts import BasketballContext, AgentOpinion

class PossessionSimulatorAgent:
    name="possession-monte-carlo"
    def run(self,ctx:BasketballContext,base_margin:float,base_total:float,sims:int=20000)->AgentOpinion:
        h=ctx.team_stats.get(ctx.home,{ }); a=ctx.team_stats.get(ctx.away,{ }); pace=max(70,min(110,(float(h.get("pace",99))+float(a.get("pace",99)))/2)); vol=max(8,float(ctx.market.get("score_sd",11)))
        hs=[]; as_=[]
        for _ in range(sims):
            p=max(60,min(120,random.gauss(pace,3))); total=max(120,random.gauss(base_total,vol*math.sqrt(p/100)))
            margin=random.gauss(base_margin,vol*.55); hs.append((total+margin)/2); as_.append((total-margin)/2)
        hm=sum(x>y for x,y in zip(hs,as_))/sims; margins=[x-y for x,y in zip(hs,as_)]
        return AgentOpinion(self.name,"SIMULATED_DISTRIBUTION",min(.96,.60+abs(hm-.5)),fair_margin=sum(margins)/sims,fair_total=sum(hs[i]+as_[i] for i in range(sims))/sims,win_prob_home=hm,rationale=["Correlated pace, total, and margin shocks are simulated rather than treating final scores as independent Poisson goals."],evidence={"simulations":sims,"margin_p10":sorted(margins)[int(.10*sims)],"margin_p90":sorted(margins)[int(.90*sims)]})
