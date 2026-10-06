from basketball_omega.contracts import BasketballContext, AgentOpinion

class LineupAgent:
    name="lineup-synergy"
    def run(self,ctx:BasketballContext)->AgentOpinion:
        scores={ctx.home:0.0,ctx.away:0.0}; samples={}
        for team,rows in ctx.lineups.items():
            for x in rows:
                n=float(x.get("minutes",0) or 0); net=float(x.get("net_rating",0) or 0)
                w=min(1.0,n/200.0); scores[team]+=net*w; samples[team]=samples.get(team,0)+n
        margin=scores.get(ctx.home,0)-scores.get(ctx.away,0)
        return AgentOpinion(self.name,"LINEUP_EDGE",min(0.92,0.52+abs(margin)/25),fair_margin=margin,rationale=["Five-man evidence is shrunk by observed lineup minutes to reduce small-sample overreaction."],risks=["Sparse lineup samples reduce reliability."] if min(samples.values() or [0])<200 else [],evidence={"lineup_scores":scores,"samples":samples})
