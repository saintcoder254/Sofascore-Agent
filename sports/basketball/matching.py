from __future__ import annotations
import re
import unicodedata
from datetime import datetime, timezone

def normalize_team_name(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    aliases = {"la clippers": "los angeles clippers", "ny knicks": "new york knicks",
               "gs warriors": "golden state warriors"}
    value = aliases.get(value, value)
    return " ".join(value.split())

def match_fixture(home_a: str, away_a: str, tip_a: float,
                  home_b: str, away_b: str, tip_b: float,
                  max_minutes: int = 30) -> bool:
    if normalize_team_name(home_a) != normalize_team_name(home_b):
        return False
    if normalize_team_name(away_a) != normalize_team_name(away_b):
        return False
    return abs(float(tip_a) - float(tip_b)) <= max_minutes * 60
