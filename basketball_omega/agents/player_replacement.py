"""Translate missing player minutes into uncertainty-aware team impact."""
from basketball_omega.agents.minutes_distribution import MinutesDistributionAgent

class PlayerReplacementAgent:
    name="basketball-player-replacement"

    def __init__(self):
        self.minutes=MinutesDistributionAgent()

    def estimate(self, players, injuries):
        forecasts={}
        total_expected=0.0
        replacement_minutes=0.0
        for p in players:
            pid=str(p.get("player_id"))
            f=self.minutes.forecast(p,injuries.get(pid))
            forecasts[pid]=f
            total_expected += f.mean
            if f.availability_probability < 1.0:
                replacement_minutes += max(0.0,float(p.get("expected_minutes",p.get("minutes",0)))-f.mean)
        return {
            "forecasts":forecasts,
            "expected_available_minutes":total_expected,
            "replacement_minutes_needed":replacement_minutes,
            "replacement_chain": {
                pid:self.minutes.replacement_chain(players,pid)
                for pid,f in forecasts.items() if f.availability_probability < 1.0
            },
        }
