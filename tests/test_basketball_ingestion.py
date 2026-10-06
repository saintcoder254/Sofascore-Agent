from basketball_omega.ingestion.contracts import SourceRecord
from basketball_omega.ingestion.engine import BasketballIngestionEngine
from basketball_omega.ingestion.archive import RawEvidenceArchive

def rec(source,key,at,payload):
    return SourceRecord(source,"endpoint",key,at,payload,"raw")

def test_pit_rejects_future_effective_and_capture_times():
    engine=BasketballIngestionEngine()
    rows=[
      rec("nba_stats","g1",100,{"entity_type":"game","entity_id":"g1","game_id":"g1","home_team_id":"H","away_team_id":"A","game_time":100,"status":"final","home_score":110,"away_score":100,"effective_at":90}),
      rec("nba_stats","future",200,{"entity_type":"player","entity_id":"p1","game_id":"g1","team_id":"H","effective_at":200,"minutes":30}),
    ]
    snap=engine.pit_snapshot(rows,100)
    assert len(snap.records)==1 and snap.records[0].entity_id=="g1"

def test_cross_source_conflict_is_flagged():
    engine=BasketballIngestionEngine()
    rows=[
      rec("nba_stats","g1",100,{"entity_type":"game","entity_id":"g1","game_id":"g1","home_team_id":"H","away_team_id":"A","game_time":100,"status":"final","home_score":110,"away_score":100}),
      rec("basketball_reference","g1",101,{"entity_type":"game","entity_id":"g1","game_id":"g1","home_team_id":"H","away_team_id":"A","game_time":100,"status":"final","home_score":111,"away_score":100}),
    ]
    result=engine.ingest(rows)
    assert any(i.code=="SOURCE_CONFLICT" for i in result.issues)

def test_quality_rejects_negative_minutes():
    engine=BasketballIngestionEngine()
    result=engine.ingest([rec("nba_stats","p",100,{"entity_type":"player","entity_id":"p","game_id":"g","team_id":"H","effective_at":100,"minutes":-1})])
    assert any(i.code=="NEGATIVE_MINUTES" for i in result.issues)

def test_archive_is_content_addressed():
    seen={}
    archive=RawEvidenceArchive(lambda k,b,m: seen.update({k:(b,m)}))
    key,digest=archive.archive("nba_stats","x",{"a":1},100)
    assert digest in key and seen[key][1]["sha256"]==digest
