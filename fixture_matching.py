import re
import unicodedata
from difflib import SequenceMatcher


class FixtureMatcher:
    """Cross-source fixture identity resolver with aliases and conservative fuzzy matching."""

    STOP = {"fc", "cf", "sc", "afc", "ac", "club", "football", "soccer", "women", "w"}
    ALIASES = {
        "manchester united": {"man united", "man utd", "manchester utd", "manchester united fc"},
        "manchester city": {"man city", "manchester city fc"},
        "tottenham hotspur": {"tottenham", "spurs", "tottenham hotspur fc"},
        "newcastle united": {"newcastle", "newcastle utd", "newcastle united fc"},
        "west ham united": {"west ham", "west ham utd"},
        "nottingham forest": {"nottm forest", "nottingham forest fc"},
        "brighton and hove albion": {"brighton", "brighton hove albion"},
        "wolverhampton wanderers": {"wolves", "wolverhampton", "wolverhampton wanderers fc"},
        "inter milan": {"inter", "internazionale", "inter milano"},
        "ac milan": {"milan", "ac milan fc"},
        "paris saint germain": {"psg", "paris sg", "paris saint-germain"},
        "atletico madrid": {"atletico", "atletico de madrid", "ath madrid"},
        "real madrid": {"real madrid cf", "real madrid fc"},
        "bayern munich": {"bayern", "bayern munchen", "fc bayern munich"},
        "borussia dortmund": {"dortmund", "bvb"},
        "sporting cp": {"sporting lisbon", "sporting lisboa", "sporting"},
        "psv eindhoven": {"psv", "psv eindhoven fc"},
    }

    def __init__(self, time_tolerance_minutes=180, fuzzy_threshold=0.90):
        self.time_tolerance = int(time_tolerance_minutes) * 60
        self.fuzzy_threshold = float(fuzzy_threshold)
        self.alias_to_canonical = {}
        for canonical, aliases in self.ALIASES.items():
            self.alias_to_canonical[self._basic(canonical)] = canonical
            for alias in aliases:
                self.alias_to_canonical[self._basic(alias)] = canonical

    @staticmethod
    def _basic(value):
        value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
        value = re.sub(r"&", " and ", value)
        value = re.sub(r"[^a-z0-9 ]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    def team_key(self, value):
        basic = self._basic(value)
        canonical = self.alias_to_canonical.get(basic, basic)
        tokens = [x for x in canonical.split() if x not in self.STOP]
        return " ".join(tokens)

    def team_similarity(self, left, right):
        a, b = self.team_key(left), self.team_key(right)
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        return SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _timestamp(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace("Z", "+00:00")
        try:
            from datetime import datetime
            return datetime.fromisoformat(text).timestamp()
        except (ValueError, TypeError):
            return None

    def match_score(self, home_a, away_a, home_b, away_b, kickoff_a=None, kickoff_b=None):
        home = self.team_similarity(home_a, home_b)
        away = self.team_similarity(away_a, away_b)
        if home < self.fuzzy_threshold or away < self.fuzzy_threshold:
            return {"matched": False, "score": min(home, away), "reason": "team mismatch", "home_similarity": home, "away_similarity": away}
        ta, tb = self._timestamp(kickoff_a), self._timestamp(kickoff_b)
        time_score = 1.0
        if ta is not None and tb is not None:
            delta = abs(ta - tb)
            if delta > self.time_tolerance:
                return {"matched": False, "score": min(home, away), "reason": "kickoff outside tolerance", "home_similarity": home, "away_similarity": away, "kickoff_delta_seconds": delta}
            time_score = max(0.0, 1.0 - delta / self.time_tolerance)
        score = 0.45 * home + 0.45 * away + 0.10 * time_score
        return {"matched": score >= self.fuzzy_threshold, "score": score, "reason": "matched" if score >= self.fuzzy_threshold else "low confidence", "home_similarity": home, "away_similarity": away, "kickoff_delta_seconds": None if ta is None or tb is None else abs(ta - tb)}

    def find(self, event, candidates):
        eh, ea = (event.get("homeTeam") or {}).get("name"), (event.get("awayTeam") or {}).get("name")
        ek = event.get("date") or event.get("kickoff")
        matches = []
        for candidate in candidates or []:
            ch, ca = (candidate.get("homeTeam") or {}).get("name"), (candidate.get("awayTeam") or {}).get("name")
            score = self.match_score(eh, ea, ch, ca, ek, candidate.get("date") or candidate.get("kickoff"))
            if score["matched"]:
                matches.append((score["score"], candidate, score))
        matches.sort(key=lambda x: x[0], reverse=True)
        return matches
