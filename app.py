import asyncio, os, time, logging, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from feed_fusion import FeedFusionAdapter
from integrity import FreshnessGate, ConflictGate
from store import Store
from evolution import EvolutionAgent
from research_engine import ResearchEngine
from learning_loop import ClosedLoopLearning
from source_learning import SourceLearningAgent
from odds_intelligence import OddsIntelligenceAgent
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger=logging.getLogger("emm.poller")
POLL_SECONDS=int(os.getenv("POLL_SECONDS","60")); STALE_AFTER=int(os.getenv("STALE_AFTER_SECONDS","180")); BASE=os.getenv("SOFASCORE_BASE","https://www.sofascore.com/api/v1"); DB=os.getenv("DATABASE_PATH","matchmaster.db"); TIMEOUT=float(os.getenv("HTTP_TIMEOUT_SECONDS","15")); EVOLUTION_SECONDS=int(os.getenv("EVOLUTION_SECONDS","21600")); EVOLUTION_MIN_SAMPLES=int(os.getenv("EVOLUTION_MIN_SAMPLES","100")); RESEARCH_SECONDS=int(os.getenv("RESEARCH_SECONDS","21600")); LEARNING_SECONDS=int(os.getenv("LEARNING_SECONDS","300")); SOURCE_LEARNING_SECONDS=int(os.getenv("SOURCE_LEARNING_SECONDS","300")); SOURCE_MIN_SAMPLES=int(os.getenv("SOURCE_MIN_SAMPLES","100"))
adapter=FeedFusionAdapter(BASE,TIMEOUT); store=Store(DB); fresh=FreshnessGate(STALE_AFTER); conflict=ConflictGate(); evolution=EvolutionAgent(store,EVOLUTION_MIN_SAMPLES); research=ResearchEngine(store); learning=ClosedLoopLearning(store,evolution); source_learning=SourceLearningAgent(store,SOURCE_MIN_SAMPLES); odds=OddsIntelligenceAgent(store)
state={"last_poll":None,"last_success":None,"last_error":None,"last_poll_duration_ms":None,"last_poll_items":0,"polls_total":0,"polls_success":0,"polls_failed":0,"consecutive_failures":0,"next_poll_at":None,"items":0,"running":False,"evolution_running":False,"last_evolution_at":None,"research_running":False,"last_research_at":None,"learning_running":False,"last_learning_at":None,"source_learning_running":False,"last_source_learning_at":None,"active_source":None}
class PredictionIn(BaseModel):
    prediction_id:str=Field(default_factory=lambda:str(uuid.uuid4())); fixture_id:str; market:str; predicted_probability:float=Field(ge=0,le=1); selection:str|None=None; odds:float|None=Field(default=None,gt=1); model_version:str="unknown"; features:dict=Field(default_factory=dict)
class PredictionBatchIn(BaseModel): predictions:list[PredictionIn]=Field(min_length=1,max_length=500)
class OutcomeIn(BaseModel): outcome:float=Field(ge=0,le=1)
async def poll_once():
    started=time.perf_counter(); state["last_poll"]=time.time(); state["polls_total"]+=1; poll_no=state["polls_total"]
    try:
        data=await adapter.today_events(); source=data.get("source",adapter.active_source or "unknown"); state["active_source"]=source; events=data.get("events",[]); stored=skipped=0; conflicts=data.get("verification_conflicts",[]) or []; conflict_ids={str(x.get("active_id")) for x in conflicts}
        for event in events:
            eid=str(event.get("id",""))
            if not eid:skipped+=1;continue
            event["verification"]={"source":"futbol24","checked_at":data.get("verification",{}).get("futbol24",{}).get("retrieved_at"),"conflict":eid in conflict_ids}; prev=store.get_current(eid); conflict.compare(prev["payload"] if prev else None,event); store.put(eid,time.time(),adapter.payload_hash(event)); stored+=1
        s24=data.get("verification",{}).get("scores24",{}) or {}; s24_added=store.add_external_observations("scores24",s24.get("observations",[]),s24.get("retrieved_at")); duration=round((time.perf_counter()-started)*1000,1); state.update({"items":len(events),"last_poll_items":stored,"last_success":time.time(),"last_error":None,"last_poll_duration_ms":duration,"polls_success":state["polls_success"]+1,"consecutive_failures":0}); logger.info("POLL_SUCCESS number=%s source=%s events=%s stored=%s scores24=%s conflicts=%s duration_ms=%s",poll_no,source,len(events),stored,s24_added,len(conflicts),duration);return len(events)
    except Exception as exc:
        duration=round((time.perf_counter()-started)*1000,1);state.update({"last_error":repr(exc),"last_poll_duration_ms":duration,"polls_failed":state["polls_failed"]+1,"consecutive_failures":state["consecutive_failures"]+1});logger.error("POLL_FAILED number=%s error=%r",poll_no,exc);raise
async def polling_loop():
    state["running"]=True;backoff=POLL_SECONDS
    while True:
        try:await poll_once();backoff=POLL_SECONDS;state["next_poll_at"]=time.time()+backoff
        except Exception:backoff=min(max(POLL_SECONDS,backoff*2),900);state["next_poll_at"]=time.time()+backoff
        await asyncio.sleep(backoff)
async def evolution_loop():
    state["evolution_running"]=True
    while True:
        try:r=evolution.run_cycle(reason="scheduled");state["last_evolution_at"]=r["created_at"]
        except Exception as exc:logger.error("EVOLUTION_CYCLE_FAILED error=%r",exc)
        await asyncio.sleep(EVOLUTION_SECONDS)
async def research_loop():
    state["research_running"]=True
    while True:
        try:r=research.research_report();state["last_research_at"]=r["generated_at"]
        except Exception as exc:logger.error("RESEARCH_CYCLE_FAILED error=%r",exc)
        await asyncio.sleep(RESEARCH_SECONDS)
async def learning_loop():
    state["learning_running"]=True
    while True:
        try:r=learning.run(reason="scheduled");state["last_learning_at"]=r["created_at"]
        except Exception as exc:logger.error("LEARNING_CYCLE_FAILED error=%r",exc)
        await asyncio.sleep(LEARNING_SECONDS)
async def source_learning_loop():
    state["source_learning_running"]=True
    while True:
        try:r=source_learning.run();state["last_source_learning_at"]=r["created_at"];logger.info("SOURCE_LEARNING_CYCLE resolved=%s scored=%s",r["resolution"]["resolved"],len(r["scores"]))
        except Exception as exc:logger.error("SOURCE_LEARNING_CYCLE_FAILED error=%r",exc)
        await asyncio.sleep(SOURCE_LEARNING_SECONDS)
@asynccontextmanager
async def lifespan(app):
    tasks=[asyncio.create_task(x()) for x in (polling_loop,evolution_loop,research_loop,learning_loop,source_learning_loop)];yield
    for t in tasks:t.cancel()
    await asyncio.gather(*tasks,return_exceptions=True);state.update({"running":False,"evolution_running":False,"research_running":False,"learning_running":False,"source_learning_running":False});await adapter.close()
app=FastAPI(title="Elite MatchMaster Feed Fusion Acquisition Agent",lifespan=lifespan)
def telemetry_payload():
    now=time.time();age=None if state["last_success"] is None else round(now-state["last_success"],1);fresh_enough=state["last_success"] is not None and age<=STALE_AFTER
    return {"service":"feed-fusion-acquisition-agent","source":state["active_source"] or adapter.active_source,"running":state["running"],"poll_interval_seconds":POLL_SECONDS,"stale_after_seconds":STALE_AFTER,"last_success_age_seconds":age,"data_fresh":fresh_enough,"ingestion_verified":bool(fresh_enough and state["polls_success"]>0),"poller":dict(state),"fusion":dict(adapter.metrics),"primary_sofascore":dict(adapter.primary_metrics),"scores24":dict(adapter.scores24.metrics),"evolution":evolution.status(),"research":{"running":state["research_running"],"last_research_at":state["last_research_at"]},"learning":{"running":state["learning_running"],"last_learning_at":state["last_learning_at"],"prediction_count":store.prediction_count(),"resolved_count":store.resolved_prediction_count(),"performance":store.performance_summary(),"scores24_observations":store.external_summary("scores24")},"source_learning":{"running":state["source_learning_running"],"last_run_at":state["last_source_learning_at"],"min_samples":SOURCE_MIN_SAMPLES,"scores":source_learning.status()},"odds_intelligence":{"fixtures_with_odds":odds.snapshot()["fixtures_with_odds"]},"generated_at":now}
@app.get("/health")
async def health():t=telemetry_payload();return {"ok":t["data_fresh"],**t}
@app.get("/status")
async def status():return telemetry_payload()
@app.get("/telemetry")
async def telemetry():return telemetry_payload()
@app.get("/evolution")
async def evolution_status():return evolution.status()
@app.post("/evolution/run")
async def evolution_run():return evolution.run_cycle(reason="manual")
@app.get("/research")
async def research_status():return research.research_report()
@app.post("/research/run")
async def research_run():return research.research_report()
@app.post("/predictions")
async def record_prediction(item:PredictionIn):store.add_prediction(prediction_id=item.prediction_id,fixture_id=item.fixture_id,market=item.market,predicted_probability=item.predicted_probability,selection=item.selection,odds=item.odds,model_version=item.model_version,features=item.features);return {"ok":True,"prediction_id":item.prediction_id}
@app.post("/predictions/batch")
async def record_prediction_batch(item:PredictionBatchIn):
    for p in item.predictions:store.add_prediction(prediction_id=p.prediction_id,fixture_id=p.fixture_id,market=p.market,predicted_probability=p.predicted_probability,selection=p.selection,odds=p.odds,model_version=p.model_version,features=p.features)
    return {"ok":True,"recorded":len(item.predictions),"prediction_ids":[p.prediction_id for p in item.predictions]}
@app.post("/predictions/umios")
async def record_umios_predictions(item:PredictionBatchIn):
    for p in item.predictions:store.add_prediction(prediction_id=p.prediction_id,fixture_id=p.fixture_id,market=p.market,predicted_probability=p.predicted_probability,selection=p.selection,odds=p.odds,model_version=p.model_version,features=p.features)
    return {"ok":True,"source":"umios","recorded":len(item.predictions),"prediction_ids":[p.prediction_id for p in item.predictions]}
@app.post("/predictions/{prediction_id}/outcome")
async def record_outcome(prediction_id:str,item:OutcomeIn):store.record_outcome(prediction_id,item.outcome);return {"ok":True,"prediction_id":prediction_id,"outcome":item.outcome}
@app.get("/learning")
async def learning_status():return {"agent":"Closed-Loop Learning Core","interval_seconds":LEARNING_SECONDS,"running":state["learning_running"],"last_learning_at":state["last_learning_at"],"prediction_count":store.prediction_count(),"resolved_count":store.resolved_prediction_count(),"performance":store.performance_summary(),"scores24":store.external_summary("scores24"),"evolution":evolution.status()}
@app.post("/learning/run")
async def learning_run():return learning.run(reason="manual")
@app.get("/learning/performance")
async def learning_performance():return store.performance_summary()
@app.get("/learning/sources")
async def learning_sources():return {"agent":"Source Reliability Agent","min_samples":SOURCE_MIN_SAMPLES,"scores":source_learning.status()}
@app.post("/learning/sources/run")
async def learning_sources_run():return source_learning.run()
@app.get("/odds")
async def odds_status():return odds.status()
@app.post("/odds/compare")
async def odds_compare(model_probability:float=Field(ge=0,le=1),odds_value:float=Field(gt=1)):return odds.compare(model_probability,odds_value)
@app.get("/sources/scores24")
async def scores24_status():return {"source":"scores24","url":adapter.scores24.URL,"methodology":adapter.scores24.METHODOLOGY,"metrics":adapter.scores24.metrics,"stored":store.external_summary("scores24")}
@app.get("/live")
async def live():return {"count":len(store.current()),"items":store.current(),"source":state["active_source"] or adapter.active_source}
@app.get("/fixture/{event_id}")
async def fixture(event_id:str):
    row=store.get_current(event_id)
    if not row:raise HTTPException(404,"fixture not cached")
    s,a,r=fresh.evaluate(row["retrieved_at"]);return {"fixture_id":event_id,"integrity":{"status":s,"age_seconds":a,"reason":r},"data":row}
@app.get("/events/today")
async def events_today():return await adapter.today_events()
@app.post("/poll")
async def manual_poll():return {"ok":True,"items":await poll_once(),"retrieved_at":time.time(),"source":state["active_source"],"telemetry":telemetry_payload()}
@app.get("/fusion/feed")
async def fusion_feed():
    output=[]
    for row in store.current():
        s,a,r=fresh.evaluate(row["retrieved_at"]);output.append({"fixture_id":row["fixture_id"],"eligible":s=="FRESH","integrity_status":s,"age_seconds":a,"reason":r,"data":row["payload"] if s=="FRESH" else None})
    return {"source":state["active_source"] or adapter.active_source,"generated_at":time.time(),"telemetry":telemetry_payload(),"items":output}
