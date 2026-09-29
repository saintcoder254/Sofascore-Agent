"""Competition-specific volatility/regime classification."""
import re
class CompetitionRegimeAgent:
    VERSION="EMM-CSVR-v2.0"
    def classify(self,event,evidence):
        text=" ".join(str(event.get(k,"")) for k in ("tournamentName","category","sport","sportName","eventType")).lower()
        if any(x in text for x in ("u20","u18","u19","youth","junior","reserve","2nd team","b team")):
            return {"regime":"YOUTH_RESERVE_HIGH_VOLATILITY","multiplier":1.35,"min_history":8,"status":"RESTRICTED"}
        if any(x in text for x in ("friendly","club friendlies","preseason")):
            return {"regime":"FRIENDLY_HIGH_UNCERTAINTY","multiplier":1.25,"min_history":7,"status":"RESTRICTED"}
        return {"regime":"STANDARD","multiplier":1.0,"min_history":5,"status":"NORMAL"}