from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from pathlib import Path

@dataclass(frozen=True)
class PregameRow:
    fixture_id: str
    competition: str
    scheduled_tipoff: float
    snapshot_timestamp: float
    home_team_id: str
    away_team_id: str
    features: dict
    market: dict
    target_home_win: int | None = None
    target_total: float | None = None
    verified: bool = False

class HistoricalDataset:
    """Append-only JSONL dataset contract for reproducible model training."""
    def __init__(self, path: str = "data/basketball/pregame.jsonl"):
        self.path = Path(path)

    def append(self, row: PregameRow):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(row), sort_keys=True) + "\n")

    def read_verified(self) -> list[PregameRow]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("verified"):
                rows.append(PregameRow(**data))
        return rows
