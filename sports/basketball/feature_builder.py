from __future__ import annotations
from dataclasses import dataclass
from statistics import mean

@dataclass(frozen=True)
class RollingTeamFeatures:
    games: int
    points_for: float
    points_against: float
    pace_proxy: float
    margin: float
    total_mean: float
    volatility: float

def _stats(events: list[dict], team_id: int) -> list[tuple[float, float]]:
    rows = []
    for event in events:
        home = event.get("homeScore") or {}
        away = event.get("awayScore") or {}
        if event.get("status", {}).get("type") not in {"finished", "afterpenalties"}:
            continue
        if event.get("homeTeam", {}).get("id") == team_id:
            if "current" in home and "current" in away:
                rows.append((float(home["current"]), float(away["current"])))
        elif event.get("awayTeam", {}).get("id") == team_id:
            if "current" in home and "current" in away:
                rows.append((float(away["current"]), float(home["current"])))
    return rows

def build_rolling_features(events: list[dict], team_id: int, window: int = 10) -> RollingTeamFeatures:
    rows = _stats(events, team_id)[-window:]
    if not rows:
        return RollingTeamFeatures(0, 0, 0, 0, 0, 0, 0)
    pf = [x[0] for x in rows]
    pa = [x[1] for x in rows]
    totals = [a + b for a, b in rows]
    margins = [a - b for a, b in rows]
    volatility = (sum((x - mean(totals)) ** 2 for x in totals) / len(totals)) ** 0.5 if len(totals) > 1 else 0.0
    # Possession proxy is intentionally conservative until pace statistics are ingested.
    pace_proxy = mean(totals) / 2.25
    return RollingTeamFeatures(len(rows), mean(pf), mean(pa), pace_proxy, mean(margins), mean(totals), volatility)
