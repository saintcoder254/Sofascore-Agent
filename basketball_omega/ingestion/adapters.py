"""Source-specific acquisition bots.

Adapters emit SourceRecord only; model code never consumes raw responses directly.
Network transport is injected for deterministic testing.
"""
import hashlib, json
from .contracts import SourceRecord
from .resilience import ResilientFetcher

class BaseSourceAdapter:
    source=""
    def __init__(self, fetch):
        self.fetcher=ResilientFetcher(fetch)
    def _record(self, endpoint, key, captured_at, payload):
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
        return SourceRecord(self.source,endpoint,key,float(captured_at),payload,digest)

class NBAStatsAdapter(BaseSourceAdapter):
    source="nba_stats"
    def games(self, season, payloads, captured_at):
        return [self._record(f"nba_stats/games/{season}",str(i),captured_at,p) for i,p in enumerate(payloads)]
    def play_by_play(self, game_id, payload, captured_at):
        return self._record(f"stats/playbyplayv3/{game_id}",game_id,captured_at,payload)

class NBADataArchiveAdapter(BaseSourceAdapter):
    source="nba_data_archive"
    def dataset(self, dataset_name, payloads, captured_at):
        return [self._record(f"nba_data/{dataset_name}",str(i),captured_at,p) for i,p in enumerate(payloads)]

class BasketballReferenceAdapter(BaseSourceAdapter):
    source="basketball_reference"
    def games(self, date, payloads, captured_at):
        return [self._record(f"basketball_reference/games/{date}",str(i),captured_at,p) for i,p in enumerate(payloads)]

class AcquisitionRouter:
    def __init__(self, adapters):
        self.adapters=adapters
    def adapter(self, source):
        return self.adapters[source]
