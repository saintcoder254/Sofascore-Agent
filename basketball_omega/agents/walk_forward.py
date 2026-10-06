"""Chronological walk-forward training and evaluation for Basketball OMEGA."""
from dataclasses import dataclass, asdict
import math
from basketball_omega.agents.opponent_adjustment import OpponentTeammateAdjustmentAgent
from basketball_omega.agents.player_state import PlayerStateAgent

@dataclass(frozen=True)
class WalkForwardRow:
    fixture_id: str
    cutoff_at: float
    predicted_home_prob: float
    predicted_margin: float
    predicted_total: float
    actual_home_win: int
    actual_margin: float
    actual_total: float
    entry_spread: float | None = None
    closing_spread: float | None = None

class BasketballWalkForwardTrainer:
    """Expanding-window OOS evaluator. No row after cutoff may enter training."""

    def __init__(self, min_train=50, recalibrate_every=1):
        self.min_train=max(1,int(min_train))
        self.recalibrate_every=max(1,int(recalibrate_every))
        self.adjuster=OpponentTeammateAdjustmentAgent()
        self.state_agent=PlayerStateAgent()

    @staticmethod
    def _sigmoid(x):
        x=max(-35.0,min(35.0,float(x)))
        return 1.0/(1.0+math.exp(-x))

    def _train_state(self, rows):
        obs=[]
        for ex in rows:
            for p in ex.features.get("players",{}).values():
                history=p.get("impact_history") or []
                for h in history:
                    obs.append({"player_id":p.get("player_id", ""), "impact":h.get("impact",0),
                                "sample_size":h.get("sample_size",1), "team_id":p.get("team_id",""),
                                "opponent_id":h.get("opponent_id","")})
        adjusted=self.adjuster.fit(obs)
        return adjusted

    def _predict(self, ex, adjusted):
        teams=ex.features.get("teams",{})
        h=teams.get(ex.home_team_id,{ }); a=teams.get(ex.away_team_id,{ })
        h_off=float(h.get("ortg",h.get("off_rating",110))); a_off=float(a.get("ortg",a.get("off_rating",110)))
        h_def=float(h.get("drtg",h.get("def_rating",110))); a_def=float(a.get("drtg",a.get("def_rating",110)))
        pace=(float(h.get("pace",99))+float(a.get("pace",99)))/2
        base_margin=((h_off-a_def)-(a_off-h_def))*pace/100.0/2.0
        p_h=0.0; p_a=0.0
        for pid,p in ex.features.get("players",{}).items():
            team=str(p.get("team_id",""))
            e=adjusted.get(str(pid))
            if not e: continue
            mins=float(p.get("expected_minutes",24) or 0)
            if team==ex.home_team_id: p_h += e.adjusted_impact*mins/48
            elif team==ex.away_team_id: p_a += e.adjusted_impact*mins/48
        lineup_h = [x for x in ex.features.get("lineups", []) if str(x.get("team_id")) == str(ex.home_team_id)]
        lineup_a = [x for x in ex.features.get("lineups", []) if str(x.get("team_id")) == str(ex.away_team_id)]
        def lineup_signal(rows):
            weighted=[]; weights=[]
            for x in rows:
                w=max(1.0, float(x.get("possessions", x.get("expected_minutes", 0)) or 0))
                weighted.append(float(x.get("net_rating", 0.0))*w); weights.append(w)
            return sum(weighted)/sum(weights) if weights else 0.0
        margin=base_margin+p_h-p_a+0.20*(lineup_signal(lineup_h)-lineup_signal(lineup_a))
        total=pace*(h_off+a_off+h_def+a_def)/440.0*200.0
        prob=self._sigmoid(margin/7.0)
        return prob, margin, total

    def run(self, examples):
        rows=sorted(examples,key=lambda x:(x.cutoff_at,x.fixture_id))
        if len(rows)<=self.min_train: return []
        out=[]
        for i in range(self.min_train,len(rows)):
            train=rows[:i]
            adjusted=self._train_state(train)
            ex=rows[i]
            p,m,t=self._predict(ex,adjusted)
            market=ex.features.get("markets",[])
            entry=next((float(x["line"]) for x in market if x.get("market")=="spread" and x.get("is_opening")),None)
            close=next((float(x["line"]) for x in market if x.get("market")=="spread" and x.get("is_closing")),None)
            out.append(WalkForwardRow(ex.fixture_id,ex.cutoff_at,p,m,t,ex.target_home_win,ex.target_margin,ex.target_total,entry,close))
        return out
