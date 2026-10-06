from dataclasses import dataclass, field

@dataclass
class BasketballDigitalTwin:
    fixture_id:str
    cutoff_at:float
    teams:dict
    players:dict
    lineups:list=field(default_factory=list)
    injuries:dict=field(default_factory=dict)
    market:dict=field(default_factory=dict)
    regime:dict=field(default_factory=dict)
    uncertainty:dict=field(default_factory=dict)

    def state(self):
        return {"fixture_id":self.fixture_id,"cutoff_at":self.cutoff_at,"teams":self.teams,
                "players":self.players,"lineups":self.lineups,"injuries":self.injuries,
                "market":self.market,"regime":self.regime,"uncertainty":self.uncertainty}

    def assert_pit(self, captured_at):
        if float(self.cutoff_at)>float(captured_at):
            raise ValueError("digital_twin_cutoff_after_capture")
        for p in self.players.values():
            if float(p.get("effective_at",0))>self.cutoff_at or float(p.get("captured_at",0))>self.cutoff_at:
                raise ValueError("future_player_state")
        return True
