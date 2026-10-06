from basketball_omega.contracts import BasketballContext
from basketball_omega.agents import PlayerImpactAgent,MinutesAgent,LineupAgent,PossessionAgent,MatchupAgent,MarketResidualAgent,PossessionSimulatorAgent,CalibrationAgent,AdversarialAgent,RegimeAgent,CLVAgent,BasketballFinalArbiter
from basketball_omega.agents.player_state import PlayerStateAgent
from basketball_omega.agents.minutes_distribution import MinutesDistributionAgent
from basketball_omega.agents.player_replacement import PlayerReplacementAgent
from basketball_omega.agents.lineup_interaction import LineupInteractionAgent
from basketball_omega.config import BasketballOmegaConfig

class BasketballOmegaOrchestrator:
    def __init__(self,config=None):
        self.config=config or BasketballOmegaConfig()
        self.player_state=PlayerStateAgent()
        self.minutes_distribution=MinutesDistributionAgent()
        self.replacement=PlayerReplacementAgent()
        self.lineup_interaction=LineupInteractionAgent()

    def _player_state_bundle(self,ctx):
        states={}
        for pid,p in ctx.players.items():
            history=p.get("impact_history") or []
            if history:
                states[pid]=self.player_state.from_history(pid,history)
            else:
                states[pid]=self.player_state.update(None,float(p.get("impact_prior",0.0)),max(1,int(p.get("sample_size",1))))
        return states

    def _rotation_bundle(self,ctx):
        teams={}
        for team_id in (ctx.home,ctx.away):
            roster=[dict(p,player_id=pid) for pid,p in ctx.players.items()
                    if str(p.get("team",team_id))==str(team_id)]
            injuries={pid:v for pid,v in ctx.injuries.items() if pid in {str(x.get("player_id")) for x in roster}}
            teams[team_id]=self.replacement.estimate(roster,injuries)
        return teams

    def run(self,ctx:BasketballContext):
        opinions=[]
        regime=RegimeAgent().run(ctx); opinions.append(regime)
        evidence_ok=bool(ctx.team_stats.get(ctx.home)) and bool(ctx.team_stats.get(ctx.away)) and len(ctx.history)>=self.config.min_history
        if not evidence_ok:
            v=BasketballFinalArbiter().decide(opinions,ctx.market,self.config.max_agent_disagreement,self.config.min_edge,False)
            v.audit={"pipeline":"BASKETBALL-OMEGA-FUSION-v1","evidence_gate":"BLOCKED"}; return v

        states=self._player_state_bundle(ctx)
        rotations=self._rotation_bundle(ctx)
        ctx.market={**ctx.market,
                    "player_state":{pid:{"impact":s.impact,"variance":s.variance,"observations":s.observations} for pid,s in states.items()},
                    "rotation_state":rotations}

        minutes=MinutesAgent().run(ctx); impact=PlayerImpactAgent().run(ctx); lineup=LineupAgent().run(ctx); possession=PossessionAgent().run(ctx); matchup=MatchupAgent().run(ctx)
        opinions += [minutes,impact,lineup,possession,matchup]

        interaction_rows=ctx.market.get("lineup_pair_history") or {}
        for team_id, lineup_rows in ctx.lineups.items():
            for row in lineup_rows[:10]:
                ids=row.get("players") or row.get("player_ids") or []
                if len(ids)==5:
                    interaction=self.lineup_interaction.estimate(team_id,ids,interaction_rows)
                    ctx.market.setdefault("lineup_interactions",[]).append({
                        "team":team_id,"players":list(ids),"synergy":interaction.synergy,
                        "uncertainty":interaction.uncertainty,"possessions":interaction.sample_possessions
                    })

        base_margin=sum(o.fair_margin or 0 for o in (impact,lineup,possession,matchup))/4
        base_total=possession.fair_total or 220
        sim=PossessionSimulatorAgent().run(ctx,base_margin,base_total,self.config.simulations); opinions.append(sim)
        ctx.market={**ctx.market,"model_margin":sim.fair_margin,"model_total":sim.fair_total}
        opinions.append(MarketResidualAgent().run(ctx))
        if ctx.market.get("entry_spread") is not None or ctx.market.get("closing_spread") is not None:
            opinions.append(CLVAgent().run(ctx.market))
        opinions.append(AdversarialAgent().run(ctx,opinions))
        if ctx.market.get("historical_probabilities") and ctx.market.get("historical_results"):
            opinions.append(CalibrationAgent().run(ctx.market["historical_probabilities"],ctx.market["historical_results"]))
        v=BasketballFinalArbiter().decide(opinions,ctx.market,self.config.max_agent_disagreement,self.config.min_edge,True)
        v.audit={"pipeline":"BASKETBALL-OMEGA-FUSION-v1","agent_count":len(opinions),
                 "sequence":[o.agent for o in opinions],"regime":regime.verdict,
                 "evidence_gate":"PASSED","player_state_count":len(states),
                 "rotation_teams":list(rotations),"lineup_interaction_count":len(ctx.market.get("lineup_interactions",[]))}
        return v
