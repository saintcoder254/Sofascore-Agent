"""OMEGA Competition Regime Engine v1.

League/competition-specific diagnostics for scoring, draw rate, home advantage,
variance, and data reliability. No regime adjustment is applied below minimum
sample size.
"""
import math
from collections import defaultdict

class CompetitionRegimeEngine:
    VERSION="OMEGA-COMPETITION-REGIME-v1"
    def evaluate(self,matches,min_samples=30):
        rows=[m for m in matches if m.get("home_goals") is not None and m.get("away_goals") is not None]
        if len(rows)<min_samples:return {"available":False,"version":self.VERSION,"samples":len(rows),"reason":"thin_competition_sample"}
        total=[m["home_goals"]+m["away_goals"] for m in rows]
        home_w=sum(m["home_goals"]>m["away_goals"] for m in rows)/len(rows)
        draws=sum(m["home_goals"]==m["away_goals"] for m in rows)/len(rows)
        return {"available":True,"version":self.VERSION,"samples":len(rows),
                "mean_goals":sum(total)/len(total),"home_win_rate":home_w,"draw_rate":draws,
                "goal_variance":sum((x-sum(total)/len(total))**2 for x in total)/len(total)}
