from dataclasses import dataclass

@dataclass(frozen=True)
class PBPFeatureVector:
    game_id:str
    possessions:float
    pace_proxy:float
    turnovers:float
    fouls:float
    three_attempts:float
    free_throw_attempts:float
    offensive_rebounds:float
    scoring_events:int

class PBPFeatureExtractor:
    """Converts normalized play-by-play events into aggregate features."""
    def extract(self,game_id,events):
        turnovers=fouls=threes=fts=orbs=scoring=0; periods=set()
        for e in events:
            typ=str(e.get("event_type",e.get("EVENTMSGTYPE",""))).lower()
            desc=str(e.get("description",e.get("HOMEDESCRIPTION",""))).lower()
            periods.add(e.get("period",e.get("PERIOD")))
            if "turnover" in typ or "turnover" in desc: turnovers+=1
            if "foul" in typ or "foul" in desc: fouls+=1
            if "3pt" in desc or "three" in desc: threes+=1
            if "free throw" in desc or "freethrow" in desc: fts+=1
            if "offensive rebound" in desc or "oreb" in desc: orbs+=1
            if e.get("score") not in (None,""): scoring+=1
        possessions=max(1,scoring+turnovers+orbs)
        return PBPFeatureVector(str(game_id),float(possessions),float(possessions)/max(1,len(periods)),float(turnovers),float(fouls),float(threes),float(fts),float(orbs),scoring)
