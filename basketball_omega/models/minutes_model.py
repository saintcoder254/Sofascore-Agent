from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class MinutesForecast:
    player_id:str
    mean:float
    low:float
    high:float
    availability:float
    role:str

class MinutesForecaster:
    """Empirical rotation forecaster using only information available before cutoff."""
    def __init__(self, decay=0.92, min_minutes=0.0, max_minutes=48.0):
        self.decay=float(decay); self.min_minutes=min_minutes; self.max_minutes=max_minutes

    def forecast(self, player_id, history, status="available", role="rotation", teammate_out_count=0):
        vals=[float(x.get("minutes",0)) for x in history if x.get("minutes") is not None]
        if vals:
            weights=[self.decay**i for i in range(len(vals))]
            mean=sum(v*w for v,w in zip(reversed(vals),weights))/sum(weights)
            variance=sum(w*(v-mean)**2 for v,w in zip(reversed(vals),weights))/sum(weights)
        else:
            mean=24.0 if role=="rotation" else (34.0 if role=="starter" else 12.0)
            variance=36.0
        s=str(status).lower()
        availability={"out":0.0,"inactive":0.0,"questionable":0.72,"gtd":0.72,"game-time":0.72,
                       "probable":0.90,"limited":0.82}.get(s,1.0)
        if availability==0: mean=0.0
        elif teammate_out_count and s not in {"out","inactive"}:
            mean=min(48.0,mean+min(6.0,1.5*teammate_out_count))
        sd=max(2.0,sqrt(max(variance,1.0)))
        low=max(self.min_minutes,mean-1.28*sd); high=min(self.max_minutes,mean+1.28*sd)
        mean*=availability
        return MinutesForecast(str(player_id),mean,low*availability,high*availability,availability,role)

    def forecast_roster(self, players, statuses=None):
        statuses=statuses or {}
        return {str(p["player_id"]):self.forecast(
            p["player_id"],p.get("minutes_history",[]),
            statuses.get(str(p["player_id"]),p.get("status","available")),
            p.get("role","rotation"),int(p.get("teammate_out_count",0)))
            for p in players}
