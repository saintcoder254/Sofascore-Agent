from basketball_omega.contracts import BasketballContext, AgentOpinion

class PlayerImpactAgent:
    name="player-impact"
    def run(self, ctx: BasketballContext)->AgentOpinion:
        ratings={}
        for pid,p in ctx.players.items():
            box=float(p.get("impact",p.get("net_rating",0)) or 0)
            onoff=float(p.get("on_off",0) or 0)
            prior=float(p.get("prior",0) or 0)
            minutes=float(p.get("expected_minutes",p.get("minutes",0)) or 0)
            sample=float(p.get("sample",1) or 1)
            shrink=sample/(sample+20.0)
            ratings[pid]=(0.50*box+0.30*onoff+0.20*prior)*shrink
            ratings[pid]*=min(1.0,max(0.0,minutes/36.0)) if minutes else 0.0
        team={ctx.home:0.0,ctx.away:0.0}
        for pid,r in ratings.items():
            team_name=ctx.players[pid].get("team")
            if team_name in team: team[team_name]+=r
        margin=team[ctx.home]-team[ctx.away]
        return AgentOpinion(self.name,"PLAYER_EDGE",min(0.95,0.55+abs(margin)/20),fair_margin=margin,rationale=["Player impact blends current signal, on/off impact, and prior with sample-size shrinkage.","Expected minutes gate prevents inactive players from contributing full value."],evidence={"team_impact":team,"player_impact":ratings})
