from basketball_omega.contracts import BasketballContext, AgentOpinion

class PossessionAgent:
    name="possession-efficiency"
    def run(self,ctx:BasketballContext)->AgentOpinion:
        h=ctx.team_stats.get(ctx.home,{ }); a=ctx.team_stats.get(ctx.away,{ })
        pace=(float(h.get("pace",99))+float(a.get("pace",99)))/2
        ortg_h=float(h.get("ortg",115)); drtg_h=float(h.get("drtg",115)); ortg_a=float(a.get("ortg",115)); drtg_a=float(a.get("drtg",115))
        eff_h=(ortg_h+ (230-drtg_a))/2; eff_a=(ortg_a+(230-drtg_h))/2
        margin=(eff_h-eff_a)*pace/100
        total=(eff_h+eff_a)*pace/100
        return AgentOpinion(self.name,"POSSESSION_EDGE",min(.94,.55+abs(margin)/25),fair_margin=margin,fair_total=total,rationale=["Expected score is built from pace and opponent-adjusted offensive/defensive efficiency."],evidence={"pace":pace,"home_efficiency":eff_h,"away_efficiency":eff_a})
