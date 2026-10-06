from basketball_omega.contracts import BasketballContext, AgentOpinion

class MinutesAgent:
    name="minutes-projection"
    def run(self,ctx:BasketballContext)->AgentOpinion:
        uncertainty=0.0; team_minutes={ctx.home:0.0,ctx.away:0.0}
        for pid,p in ctx.players.items():
            base=float(p.get("expected_minutes",p.get("minutes",0)) or 0)
            status=str(ctx.injuries.get(pid,{}).get("status",p.get("status","available"))).lower()
            if status in {"out","inactive"}: base=0
            elif status in {"questionable","game-time","gtd"}: uncertainty+=0.04
            elif status in {"probable","limited"}: base*=0.9; uncertainty+=0.02
            team=p.get("team")
            if team in team_minutes: team_minutes[team]+=base
        gap=max(0,240-team_minutes[ctx.home])-max(0,240-team_minutes[ctx.away])
        return AgentOpinion(self.name,"MINUTES_EDGE",max(0.5,1-min(0.5,uncertainty)),rationale=["Availability is translated into minutes rather than a flat injury penalty."],risks=["Questionable players create distributional uncertainty." ] if uncertainty else [],evidence={"team_minutes":team_minutes,"injury_uncertainty":uncertainty,"replacement_minutes_gap":gap})
