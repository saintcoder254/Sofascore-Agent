from basketball_omega.contracts import BasketballContext, AgentOpinion

class RegimeAgent:
    name="regime-detector"
    def run(self,ctx:BasketballContext)->AgentOpinion:
        flags=[]
        if len(ctx.history)<12: flags.append("thin_history")
        q=sum(1 for x in ctx.injuries.values() if str(x.get("status","")).lower() in {"questionable","gtd","game-time"})
        if q: flags.append("availability_uncertainty")
        for t,s in ctx.team_stats.items():
            if s.get("back_to_back"): flags.append(f"{t}:back_to_back")
            if s.get("rest_days") is not None and float(s["rest_days"])>=3: flags.append(f"{t}:extended_rest")
        regime="high_uncertainty" if len(flags)>=2 else ("thin_sample" if "thin_history" in flags else "normal")
        return AgentOpinion(self.name,regime,.8 if regime=="normal" else .55,risks=flags,evidence={"flags":flags,"regime":regime})
