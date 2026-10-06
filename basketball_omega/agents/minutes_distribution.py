"""Expected-minutes distribution and injury replacement chain."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class MinutesForecast:
    player_id: str
    mean: float
    low: float
    high: float
    availability_probability: float
    role: str
    replacement_for: str | None = None

class MinutesDistributionAgent:
    name="basketball-minutes-distribution"

    def forecast(self, player, injury=None, context=None):
        context=context or {}
        base=float(player.get("expected_minutes",player.get("minutes",24)))
        role=str(player.get("role","rotation"))
        status=str((injury or {}).get("status",player.get("status","available"))).lower()
        availability=float((injury or {}).get("availability_probability",1.0))
        availability=max(0.0,min(1.0,availability))
        if status in {"out","inactive"}: availability=0.0
        elif status in {"doubtful"}: availability=min(availability,.25)
        elif status in {"questionable"}: availability=min(availability,.65)
        mean=base*availability
        spread=float((injury or {}).get("minutes_std",max(2.0,base*.12)))
        if status in {"questionable","doubtful"}: spread*=1.5
        low=max(0.0,mean-1.96*spread)
        high=min(48.0,mean+1.96*spread)
        return MinutesForecast(str(player.get("player_id","")),mean,low,high,availability,role)

    def replacement_chain(self, players, injured_id):
        candidates=[]
        for p in players:
            if str(p.get("player_id"))==str(injured_id): continue
            status=str(p.get("status","available")).lower()
            if status in {"out","inactive"}: continue
            candidates.append(p)
        candidates.sort(key=lambda p:(-float(p.get("replacement_priority",0)), -float(p.get("expected_minutes",p.get("minutes",0)))))
        return [str(p.get("player_id")) for p in candidates]
