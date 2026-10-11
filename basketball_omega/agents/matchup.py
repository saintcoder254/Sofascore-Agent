from basketball_omega.contracts import BasketballContext, AgentOpinion

class MatchupAgent:
    name="matchup-interaction"
    def run(self,ctx:BasketballContext)->AgentOpinion:
        h=ctx.team_stats.get(ctx.home,{ }); a=ctx.team_stats.get(ctx.away,{ })
        three=float(h.get("three_rate",0))-float(a.get("three_rate",0)); turnover=float(a.get("tov_forced",0))-float(h.get("tov_forced",0)); reb=float(h.get("oreb_rate",0))-float(a.get("oreb_rate",0))
        adjustment=2.0*three+1.5*turnover+1.2*reb
        return AgentOpinion(self.name,"MATCHUP_EDGE",min(.9,.52+abs(adjustment)/15),fair_margin=adjustment,rationale=["Matchup agent isolates structural interactions rather than reusing raw team strength."],evidence={"three_point_interaction":three,"turnover_interaction":turnover,"rebounding_interaction":reb})
