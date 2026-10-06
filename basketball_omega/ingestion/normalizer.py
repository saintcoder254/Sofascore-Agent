"""Strict normalization into point-in-time-safe canonical records."""
import hashlib
import json
from .contracts import SourceRecord, NormalizedRecord, IngestionBatch, IngestionIssue

REQUIRED_GAME={"game_id","home_team_id","away_team_id","game_time","status"}
REQUIRED_PLAYER={"player_id","team_id"}

def _stable(value):
    return json.dumps(value, sort_keys=True, separators=(",",":"), default=str)

class BasketballNormalizer:
    def normalize(self, records):
        batch=IngestionBatch()
        for r in records:
            try:
                values=dict(r.payload)
                entity_type=str(values.get("entity_type",""))
                entity_id=str(values.get("entity_id",values.get("game_id","")))
                game_id=str(values.get("game_id",""))
                effective=float(values.get("effective_at",r.observed_at))
                captured=float(r.observed_at)
                if not entity_type or not entity_id or not game_id:
                    raise ValueError("missing canonical identity")
                if effective > captured:
                    raise ValueError("effective_at_after_capture")
                if entity_type=="game" and not REQUIRED_GAME.issubset(values):
                    raise ValueError("incomplete_game_record")
                if entity_type=="player" and not REQUIRED_PLAYER.issubset(values):
                    raise ValueError("incomplete_player_record")
                checksum=hashlib.sha256(_stable(values).encode()).hexdigest()
                batch.records.append(NormalizedRecord(entity_type,entity_id,game_id,effective,captured,r.source,values,(r.checksum,checksum)))
                batch.source_counts[r.source]=batch.source_counts.get(r.source,0)+1
            except Exception as exc:
                batch.issues.append(IngestionIssue("error","NORMALIZATION_FAILED",r.source,r.record_key,str(exc)))
                batch.quarantined.append(r)
        return batch
