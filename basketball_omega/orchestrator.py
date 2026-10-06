from basketball_omega.contracts import BasketballContext, AgentOpinion
from basketball_omega.agents import PlayerImpactAgent,MinutesAgent,LineupAgent,PossessionAgent,MatchupAgent,MarketResidualAgent,PossessionSimulatorAgent,CalibrationAgent,AdversarialAgent,RegimeAgent,CLVAgent,BasketballFinalArbiter
from basketball_omega.agents.player_state import PlayerStateAgent
from basketball_omega.agents.minutes_distribution import MinutesDistributionAgent
from basketball_omega.agents.player_replacement import PlayerReplacementAgent
from basketball_omega.agents.lineup_interaction import LineupInteractionAgent
from basketball_omega.agents.player_team_impact import PlayerTeamImpactAgent
from basketball_omega.config import BasketballOmegaConfig
from basketball_omega.models import (
    RidgeRAPM, MinutesForecaster, IndependenceWeightLearner,
    BasketballDistributionEngine, MarketEngineSuite, CalibrationSuite,
    BasketballDigitalTwin,
)

class BasketballOmegaOrchestrator:
    def __init__(self,config=None):
        self.config=config or BasketballOmegaConfig()
        self.player_state=PlayerStateAgent()
        self.minutes_distribution=MinutesDistributionAgent()
        self.replacement=PlayerReplacementAgent()
        self.lineup_interaction=LineupInteractionAgent()
        self.player_team_impact=PlayerTeamImpactAgent()
        self.rapm=RidgeRAPM()
        self.minutes_forecaster=MinutesForecaster()
        self.distribution=BasketballDistributionEngine()
        self.markets=MarketEngineSuite()
        self.calibration_suite=CalibrationSuite()
        self.independence=IndependenceWeightLearner()

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
                    if str(p.get("team"))==str(team_id)]
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

        # Empirical minutes distribution is generated before player/team aggregation.
        for pid, p in ctx.players.items():
            status=ctx.injuries.get(pid,{}).get("status",p.get("status","available"))
            p["minutes_forecast"]=self.minutes_forecaster.forecast(
                pid, p.get("minutes_history",[]), status, p.get("role","rotation"),
                int(p.get("teammate_out_count",0))
            )
            p["expected_minutes"]=p["minutes_forecast"].mean
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

        projected_pace=float(possession.evidence.get("pace",100.0) or 100.0)
        player_team=self.player_team_impact.run(ctx,states,rotations,ctx.market.get("lineup_interactions",[]),projected_pace)
        opinions.append(player_team)
        base_margin=(
            0.55*(possession.fair_margin or 0.0)
            +0.15*(impact.fair_margin or 0.0)
            +0.10*(lineup.fair_margin or 0.0)
            +0.10*(matchup.fair_margin or 0.0)
            +0.10*(player_team.fair_margin or 0.0)
        )
        base_total=possession.fair_total or 220
        # Player-level RAPM-compatible evidence is an independent diagnostic.
        rapm_rows=[]
        for pid,p in ctx.players.items():
            for h in p.get("stint_history",[]) or []:
                rapm_rows.append({
                    "home_players":h.get("home_players",[pid] if h.get("team") == ctx.home else []),
                    "away_players":h.get("away_players",[pid] if h.get("team") == ctx.away else []),
                    "target":h.get("target",h.get("net_per_possession",0.0)),
                    "weight":h.get("possessions",1.0)
                })
        if rapm_rows:
            self.rapm.fit(rapm_rows)
            ctx.market["rapm"]={pid:self.rapm.estimate(pid).net for pid in ctx.players}
            opinions.append(AgentOpinion("rapm","RAPM_DIAGNOSTIC",.55,
                rationale=["Ridge plus/minus is treated as an independent diagnostic, not as an unvalidated replacement for the primary model."],
                evidence={"player_count":len(self.rapm.players),"residual_scale":self.rapm.residual_scale}))
        # Full basketball distribution is the stochastic consequence of the state.
        three_h=float(ctx.team_stats.get(ctx.home,{}).get("three_rate",.37))
        three_a=float(ctx.team_stats.get(ctx.away,{}).get("three_rate",.37))
        tov_h=float(ctx.team_stats.get(ctx.home,{}).get("tov_rate",.13))
        tov_a=float(ctx.team_stats.get(ctx.away,{}).get("tov_rate",.13))
        orb_h=float(ctx.team_stats.get(ctx.home,{}).get("orb_rate",.25))
        orb_a=float(ctx.team_stats.get(ctx.away,{}).get("orb_rate",.25))
        dist=self.distribution.simulate(
            projected_pace,
            max(80,base_margin+base_total/(2*max(projected_pace,1))*100),
            max(80,-base_margin+base_total/(2*max(projected_pace,1))*100),
            three_h,three_a,tov_h,tov_a,orb_h,orb_a,
            sims=max(1000,self.config.simulations),
            spread=ctx.market.get("spread"), total_line=ctx.market.get("total")
        )
        ctx.market["distribution"]={"home_mean":dist.home_mean,"away_mean":dist.away_mean,
            "margin_sd":dist.margin_sd,"total_sd":dist.total_sd,
            "home_win_probability":dist.home_win_probability}
        opinions.append(AgentOpinion("distribution-engine","DISTRIBUTION",.80,
            fair_margin=dist.margin_mean,fair_total=dist.total_mean,
            rationale=["Possession-level stochastic distribution includes pace, efficiency, shooting, turnovers, offensive rebounding, fouls and late variance."],
            evidence={"margin_sd":dist.margin_sd,"total_sd":dist.total_sd,"quantiles":dist.quantiles}))
        base_total=dist.total_mean
        sim=PossessionSimulatorAgent().run(ctx,base_margin,base_total,self.config.simulations); opinions.append(sim)
        ctx.market={**ctx.market,"model_margin":sim.fair_margin,"model_total":sim.fair_total,"player_team_margin":player_team.fair_margin,"player_team_uncertainty":player_team.evidence.get("uncertainty")}
        opinions.append(MarketResidualAgent().run(ctx))
        ctx.market["market_suite"]={
            "moneyline":self.markets.moneyline(dist).__dict__,
            "spread":self.markets.spread(dist,ctx.market.get("spread")).__dict__ if ctx.market.get("spread") is not None else None,
            "total":self.markets.total(dist,ctx.market.get("total")).__dict__ if ctx.market.get("total") is not None else None,
            "team_total_home":self.markets.team_total(dist.home_mean,ctx.market.get("home_team_total"),max(8.0,dist.total_sd)).__dict__ if ctx.market.get("home_team_total") is not None else None,
            "team_total_away":self.markets.team_total(dist.away_mean,ctx.market.get("away_team_total"),max(8.0,dist.total_sd)).__dict__ if ctx.market.get("away_team_total") is not None else None
        }
        if ctx.market.get("entry_spread") is not None or ctx.market.get("closing_spread") is not None:
            opinions.append(CLVAgent().run(ctx.market))
        opinions.append(AdversarialAgent().run(ctx,opinions))
        if ctx.market.get("historical_probabilities") and ctx.market.get("historical_results"):
            opinions.append(CalibrationAgent().run(ctx.market["historical_probabilities"],ctx.market["historical_results"]))
        # Digital Twin is frozen at the prediction cutoff for auditability.
        twin=BasketballDigitalTwin(
            ctx.fixture_id, float(ctx.cutoff_at or 0), ctx.team_stats, ctx.players,
            list(sum(ctx.lineups.values(),[])) if isinstance(ctx.lineups,dict) else list(ctx.lineups),
            ctx.injuries, ctx.market, {"verdict":regime.verdict},
            {"distribution_margin_sd":dist.margin_sd,"distribution_total_sd":dist.total_sd}
        )
        if ctx.cutoff_at:
            twin.assert_pit(max([float(p.get("captured_at",ctx.cutoff_at)) for p in ctx.players.values()] or [ctx.cutoff_at]))
        v=BasketballFinalArbiter().decide(opinions,ctx.market,self.config.max_agent_disagreement,self.config.min_edge,True)
        v.audit={"pipeline":"BASKETBALL-OMEGA-FUSION-v1","agent_count":len(opinions),
                 "sequence":[o.agent for o in opinions],"regime":regime.verdict,
                 "evidence_gate":"PASSED","player_state_count":len(states),
                 "rotation_teams":list(rotations),"lineup_interaction_count":len(ctx.market.get("lineup_interactions",[])),"player_team_impact":player_team.fair_margin,"player_team_uncertainty":player_team.evidence.get("uncertainty")}
        return v
