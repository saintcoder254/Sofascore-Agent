"""Player-to-team strength aggregation for Basketball OMEGA.

This layer converts point-in-time player states, expected-minute distributions,
replacement chains, and five-man interaction estimates into an explicit team
impact signal. It is an independent player/rotation view; the possession model
remains the primary team-level baseline.
"""
from dataclasses import dataclass
import math
from basketball_omega.contracts import AgentOpinion


@dataclass(frozen=True)
class TeamImpactEstimate:
    team_id: str
    strength: float
    uncertainty: float
    expected_minutes: float
    replacement_minutes: float
    interaction_adjustment: float


class PlayerTeamImpactAgent:
    name = "player-team-impact"

    def estimate(self, team_id, roster, states, rotation_state=None, interactions=None):
        rotation_state = rotation_state or {}
        interactions = interactions or []
        forecasts = rotation_state.get("forecasts", {})
        weighted = 0.0
        variance = 0.0
        minutes = 0.0
        replacement = float(rotation_state.get("replacement_minutes_needed", 0.0) or 0.0)

        for p in roster:
            pid = str(p.get("player_id"))
            f = forecasts.get(pid)
            mean_minutes = float(getattr(f, "mean", p.get("expected_minutes", p.get("minutes", 0))) or 0.0)
            state = states.get(pid)
            impact = float(getattr(state, "impact", p.get("impact", p.get("net_rating", 0.0))) or 0.0)
            state_var = float(getattr(state, "variance", p.get("impact_variance", 25.0)) or 25.0)
            if mean_minutes <= 0:
                continue
            weighted += impact * mean_minutes
            variance += state_var * (mean_minutes / 48.0) ** 2
            minutes += mean_minutes

        strength = weighted / minutes if minutes > 0 else 0.0

        interaction_total = 0.0
        interaction_var = 0.0
        for row in interactions:
            if str(row.get("team")) != str(team_id):
                continue
            interaction_total += float(row.get("synergy", 0.0) or 0.0)
            u = float(row.get("uncertainty", 0.0) or 0.0)
            interaction_var += u * u

        # Sparse lineup estimates are additive but capped so they cannot
        # overwhelm the independently estimated player strength.
        interaction_adjustment = max(-5.0, min(5.0, interaction_total))
        strength += interaction_adjustment

        uncertainty = math.sqrt(max(0.0, variance + interaction_var))
        if replacement > 0:
            # Missing minutes widen uncertainty; replacement effects are
            # handled through the explicit replacement chain.
            uncertainty += replacement * 0.08

        return TeamImpactEstimate(
            team_id=str(team_id),
            strength=strength,
            uncertainty=uncertainty,
            expected_minutes=minutes,
            replacement_minutes=replacement,
            interaction_adjustment=interaction_adjustment,
        )

    def run(self, ctx, states, rotations, interactions=None, projected_pace=None):
        interactions = interactions or []
        estimates = {}
        for team_id in (ctx.home, ctx.away):
            roster = [
                dict(p, player_id=pid)
                for pid, p in ctx.players.items()
                if str(p.get("team")) == str(team_id)
            ]
            estimates[team_id] = self.estimate(
                team_id, roster, states, rotations.get(team_id), interactions
            )

        h = estimates[ctx.home]
        a = estimates[ctx.away]
        pace = float(projected_pace or 100.0)
        margin = (h.strength - a.strength) * pace / 100.0
        uncertainty = math.sqrt(h.uncertainty ** 2 + a.uncertainty ** 2)
        confidence = max(0.20, min(0.92, 0.80 - uncertainty / 40.0))
        return AgentOpinion(
            self.name,
            "PLAYER_TEAM_EDGE",
            confidence,
            fair_margin=margin,
            rationale=[
                "Player impact is weighted by expected available minutes.",
                "Availability uncertainty widens the estimate instead of applying a fixed injury penalty.",
                "Sparse five-man interactions are shrunk and capped before entering team strength.",
            ],
            risks=[
                "This is a transparent state-estimation layer, not a trained RAPM/EPM replacement.",
            ],
            evidence={
                "team_estimates": {
                    team: {
                        "strength": e.strength,
                        "uncertainty": e.uncertainty,
                        "expected_minutes": e.expected_minutes,
                        "replacement_minutes": e.replacement_minutes,
                        "interaction_adjustment": e.interaction_adjustment,
                    }
                    for team, e in estimates.items()
                },
                "pace": pace,
                "uncertainty": uncertainty,
            },
        )
