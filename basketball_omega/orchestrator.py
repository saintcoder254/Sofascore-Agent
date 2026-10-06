from basketball_omega.contracts import BasketballContext
from basketball_omega.agents import PlayerImpactAgent,MinutesAgent,LineupAgent,PossessionAgent,MatchupAgent,MarketResidualAgent,PossessionSimulatorAgent,CalibrationAgent,AdversarialAgent,RegimeAgent,CLVAgent,BasketballFinalArbiter
from basketball_omega.config import BasketballOmegaConfig
class BasketballOmegaOrchestrator:
    def __init__(self,config=None): self.config=config or BasketballOmegaConfig()
    def run(self,ctx:BasketballContext):
        opinions=[]; regime=RegimeAgent().run(ctx); opinions.append(regime)
        evidence_ok=bool(ctx.team_stats.get(ctx.home)) and bool(ctx.team_stats.get(ctx.away)) and len(ctx.history)>=self.config.min_history
        if not evidence_ok:
            v=BasketballFinalArbiter().decide(opinions,ctx.market,self.config.max_agent_disagreement,self.config.min_edge,False); v.audit={"pipeline":"BASKETBALL-OMEGA-FUSION-v1","evidence_gate":"BLOCKED"}; return v
        minutes=MinutesAgent().run(ctx); impact=PlayerImpactAgent().run(ctx); lineup=LineupAgent().run(ctx); possession=PossessionAgent().run(ctx); matchup=MatchupAgent().run(ctx)
        opinions += [minutes,impact,lineup,possession,matchup]
        base_margin=sum(o.fair_margin or 0 for o in (impact,lineup,possession,matchup))/4; base_total=possession.fair_total or 220
        sim=PossessionSimulatorAgent().run(ctx,base_margin,base_total,self.config.simulations); opinions.append(sim)
        ctx.market={**ctx.market,"model_margin":sim.fair_margin,"model_total":sim.fair_total}
        opinions.append(MarketResidualAgent().run(ctx))
        if ctx.market.get("entry_spread") is not None or ctx.market.get("closing_spread") is not None: opinions.append(CLVAgent().run(ctx.market))
        opinions.append(AdversarialAgent().run(ctx,opinions))
        if ctx.market.get("historical_probabilities") and ctx.market.get("historical_results"): opinions.append(CalibrationAgent().run(ctx.market["historical_probabilities"],ctx.market["historical_results"]))
        v=BasketballFinalArbiter().decide(opinions,ctx.market,self.config.max_agent_disagreement,self.config.min_edge,True)
        v.audit={"pipeline":"BASKETBALL-OMEGA-FUSION-v1","agent_count":len(opinions),"sequence":[o.agent for o in opinions],"regime":regime.verdict,"evidence_gate":"PASSED"}; return v
