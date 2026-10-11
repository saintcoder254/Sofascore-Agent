from basketball_omega.ingestion.adapters import NBAStatsAdapter
from basketball_omega.ingestion.resilience import ResilientFetcher

def test_adapter_emits_hashed_source_record():
    a=NBAStatsAdapter(lambda url: {})
    r=a.games("2024-25",[{"game_id":"g"}],100)[0]
    assert r.source=="nba_stats" and len(r.checksum)==64

def test_resilient_fetch_retries_then_succeeds():
    calls=[]
    def fetch(url,**kwargs):
        calls.append(1)
        if len(calls)<3: raise TimeoutError()
        return {"ok":True}
    sleeps=[]
    out=ResilientFetcher(fetch,retries=3,sleep=lambda x:sleeps.append(x)).get("x")
    assert out["ok"] and len(calls)==3 and len(sleeps)==2
