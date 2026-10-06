from basketball_omega.contracts import BasketballContext
from basketball_omega.agents import PlayerImpactAgent,MinutesAgent,LineupAgent,PossessionAgent,MatchupAgent,MarketResidualAgent,PossessionSimulatorAgent,AdversarialAgent,BasketballFinalArbiter
from basketball_omega.config import BasketballOmegaConfig

class BasketballOmegaOrchestrator:
    """Runs independent basketball agents, exchanges evidence, then arbitrates.
    Agents do not vote blindly: the arbiter blocks on disagreement and evidence risk."""
    def __init__(self,config=None): self.config=config or BasketballOmegaConfig()
    def run(self,ctx:BasketballContext):
        opinions=[]
        minutes=MinutesAgent().run(ctx); opinions.append(minutes)
        impact=PlayerImpactAgent().run(ctx); opinions.append(impact)
        lineup=LineupAgent().run(ctx); opinions.append(lineup)
        possession=PossessionAgent().run(ctx); opinions.append(possession)
        matchup=MatchupAgent().run(ctx); opinions.append(matchup)
        base_margin=sum(o.fair_margin or 0 for o in (impact,lineup,possession,matchup))
        base_margin/=4
        base_total=possession.fair_total or 220
        sim=PossessionSimulatorAgent().run(ctx,base_margin,base_total,self.config.simulations); opinions.append(sim)
        market_ctx=ctx.market.copy(); market_ctx.update({"model_margin":sim.fair_margin,"model_total":sim.fair_total})
        ctx.market=market_ctx
        opinions.append(MarketResidualAgent().run(ctx))
        challenge=AdversarialAgent().run(ctx,opinions); opinions.append(challenge)
        verdict=BasketballFinalArbiter().decide(opinions,ctx.market,self.config.max_agent_disagreement,self.config.min_edge)
        verdict.audit={"pipeline":"BASKETBALL-OMEGA-FUSION-v1","agent_count":len(opinions),"sequence":[o.agent for o in opinions],"regime":ctx.regime}
        return verdict
