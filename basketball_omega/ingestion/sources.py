"""Source adapters and source-priority policy.

The engine deliberately treats public datasets as raw evidence, never as truth.
Primary acquisition targets:
- NBA.com Stats via nba_api: official player/team/game/PBP endpoints.
- shufinskiy/nba_data: long historical PBP, shots and matchup archive.
- Basketball-Reference web-scraper: independent game/PBP cross-check.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class SourceSpec:
    name: str
    authority: float
    capabilities: frozenset[str]
    endpoint: str

SOURCE_SPECS = (
    SourceSpec("nba_stats", 1.0, frozenset({"games","players","teams","boxscores","pbp","shots","lineups"}), "stats.nba.com"),
    SourceSpec("nba_data_archive", 0.80, frozenset({"games","pbp","shots","matchups"}), "github.com/shufinskiy/nba_data"),
    SourceSpec("basketball_reference", 0.78, frozenset({"games","pbp","players","teams"}), "basketball-reference.com"),
)

def source_for(name: str) -> SourceSpec:
    for spec in SOURCE_SPECS:
        if spec.name == name:
            return spec
    raise KeyError(name)

def source_priority(names):
    return sorted((source_for(n) for n in names), key=lambda x: x.authority, reverse=True)
