import asyncio, os, time, logging, uuid, hashlib
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
from result_verifier import ResultVerifierAgent
from verification_learning import VerificationLearningAgent
from match_acquisition import MatchAcquisitionEngine
from umios_qualifier import UMIOSQualifier
from umios_core import UMIOSCoreEngine
from umios_probability import UMIOSProbabilityEngine
from umios_arbiter import UMIOSFinalArbiter

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger=logging.getLogger("emm.poller")
POLL_SECONDS=int(os.getenv("POLL_SECONDS","60")); STALE_AFTER=int(os.getenv("STALE_AFTER_SECONDS","180")); BASE=os.getenv("SOFASCORE_BASE","https://www.sofascore.com/api/v1"); DB=os.getenv("DATABASE_PATH","matchmaster.db"); TIMEOUT=float(os.getenv("HTTP_TIMEOUT_SECONDS","15")); EVOLUTION_SECONDS=int(os.getenv("EVOLUTION_SECONDS","21600")); EVOLUTION_MIN_SAMPLES=int(os.getenv("EVOLUTION_MIN_SAMPLES","100")); RESEARCH_SECONDS=int(os.getenv("RESEARCH_SECONDS","21600")); LEARNING_SECONDS=int(os.getenv("LEARNING_SECONDS","300")); SOURCE_LEARNING_SECONDS=int(os.getenv("SOURCE_LEARNING_SECONDS","300")); SOURCE_MIN_SAMPLES=int(os.getenv("SOURCE_MIN_SAMPLES","100")); VERIFICATION_SECONDS=int(os.getenv("VERIFICATION_SECONDS","300")); VERIFICATION_MIN_SOURCES=int(os.getenv("VERIFICATION_MIN_SOURCES","2")); ENRICH_SECONDS=int(os.getenv("ENRICH_SECONDS","300")); ENRICH_MAX_FIXTURES=int(os.getenv("ENRICH_MAX_FIXTURES","8")); AUTO_ANALYZE=os.getenv("AUTO_ANALYZE","1")=="1"; AUTO_ANALYZE_MAX=int(os.getenv("AUTO_ANALYZE_MAX","8"))
adapter=FeedFusionAdapter(BASE,TIMEOUT); store=Store(DB); fresh=FreshnessGate(STALE_AFTER); conflict=ConflictGate(); evolution=EvolutionAgent(store,EVOLUTION_MIN_SAMPLES); research=ResearchEngine(store); learning=ClosedLoopLearning(store,evolution); source_learning=SourceLearningAgent(store,SOURCE_MIN_SAMPLES); odds=OddsIntelligenceAgent(store); verifier=ResultVerifierAgent(); verification_learning=VerificationLearningAgent(store,verifier,VERIFICATION_MIN_SOURCES)
acquisition=MatchAcquisitionEngine(adapter)
qualifier=UMIOSQualifier(STALE_AFTER)
core=UMIOSCoreEngine(odds)
probability=UMIOSProbabilityEngine()
arbiter=UMIOSFinalArbiter(store)
state={"last_poll":None,"last_success":None,"last_error":None,"last_poll_duration_ms":None,"last_poll_items":0,"polls_total":0,"polls_success":0,"polls_failed":0,"consecutive_failures":0,"next_poll_at":None,"items":0,"running":False,"evolution_running":False,"last_evolution_at":None,"research_running":False,"last_research_at":None,"learning_running":False,"last_learning_at":None,"source_learning_running":False,"last_source_learning_at":None,"verification_learning_running":False,"last_verification_learning_at":None,"enrichment_running":False,"last_enrichment_at":None,"enrichment_items":0,"auto_analyze_items":0,"last_auto_analyze_at":None,"arbiter_passes":0,"arbiter_blocks":0,"active_source":None}
class PredictionIn(BaseModel):
    prediction_id:str=Field(default_factory=lambda:str(uuid.uuid4())); fixture_id:str; market:str; predicted_probability:float=Field(ge=0,le=1); selection:str|None=None; odds:float|None=Field(default=None,gt=1); model_version:str="unknown"; features:dict=Field(default_factory=dict)
class PredictionBatchIn(BaseModel): predictions:list[PredictionIn]=Field(min_length=1,max_length=500)
class OutcomeIn(BaseModel): outcome:float=Field(ge=0,le=1)
async def poll_once():
    started=time.perf_counter(); state["last_poll"]=time.time(); state["polls_total"]+=1; poll_no=state["polls_total"]
    try:
        data=await adapter.today_events(); source=data.get("source",adapter.active_source or "unknown"); state["active_source"]=source; events=data.get("events",[]); stored=0; conflicts=data.get("verification_conflicts",[]) or []; conflict_ids={str(x.get("active_id")) for x in conflicts}; verification_bundle=data.get("verification",{}) or {}
        for event in events:
            eid=str(event.get("id",""))
            if not eid: continue
            event["verification"]={**verification_bundle,"event_conflict":eid in conflict_ids}; prev=store.get_current(eid); conflict.compare(prev["payload"] if prev else None,event); store.put(eid,time.time(),adapter.payload_hash(event)); stored+=1
        s24=verification_bundle.get("scores24",{}) or {}; s24_added=store.add_external_observations("scores24",s24.get("observations",[]),s24.get("retrieved_at")); duration=round((time.perf_counter()-started)*1000,1); state.update({"items":len(events),"last_poll_items":stored,"last_success":time.time(),"last_error":None,"last_poll_duration_ms":duration,"polls_success":state["polls_success"]+1,"consecutive_failures":0}); logger.info("POLL_SUCCESS source=%s events=%s stored=%s scores24=%s conflicts=%s verification_sources=%s duration_ms=%s",source,len(events),stored,s24_added,len(conflicts),len((verification_bundle.get("final_results") or {}).get("sources",[])),duration);return len(events)
    except Exception as exc:
        duration=round((time.perf_counter()-started)*1000,1);state.update({"last_error":repr(exc),"last_poll_duration_ms":duration,"polls_failed":state["polls_failed"]+1,"consecutive_failures":state["consecutive_failures"]+1});logger.error("POLL_FAILED number=%s error=%r",poll_no,exc);raise
async def polling_loop():
    state["running"]=True;backoff=POLL_SECONDS
    while True:
        try:await poll_once();backoff=POLL_SECONDS
        except Exception:backoff=min(max(POLL_SECONDS,backoff*2),900)
        state["next_poll_at"]=time.time()+backoff;await asyncio.sleep(backoff)
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
        try:r=source_learning.run();state["last_source_learning_at"]=r["created_at"]
        except Exception as exc:logger.error("SOURCE_LEARNING_CYCLE_FAILED error=%r",exc)
        await asyncio.sleep(SOURCE_LEARNING_SECONDS)
async def verification_loop():
    state["verification_learning_running"]=True
    while True:
        try:r=verification_learning.run();state["last_verification_learning_at"]=time.time();logger.info("VERIFICATION_LEARNING resolved=%s external=%s blocked=%s unresolved=%s",r["resolved"],r.get("external_resolved",0),r["blocked_conflicts"],r["unresolved"])
        except Exception as exc:logger.error("VERIFICATION_LEARNING_FAILED error=%r",exc)
        await asyncio.sleep(VERIFICATION_SECONDS)
async def enrichment_loop():
    """Continuously enrich bounded fixtures and route qualified candidates through the final arbiter."""
    state["enrichment_running"]=True
    while True:
        try:
            data=await adapter.today_events()
            events=data.get("events",[])
            now=time.time(); candidates=[]
            for event in events:
                eid=str(event.get("id",""))
                if not eid: continue
                raw_date=event.get("startTimestamp") or event.get("timestamp") or event.get("date")
                try:
                    ts=float(raw_date); ts=ts/1000 if ts>1e12 else ts
                except (TypeError,ValueError): ts=None
                if ts is not None and ts < now-7200: continue
                candidates.append((abs((ts or now)-now),eid))
            candidates=sorted(candidates)[:ENRICH_MAX_FIXTURES]
            enriched=0; passes=0; blocks=0
            for _,eid in candidates:
                try:
                    bundle=await acquisition.acquire(eid)
                    event=bundle.get("event") or {}
                    if not event: continue
                    store.put(eid,bundle.get("retrieved_at",time.time()),adapter.payload_hash(event),event)
                    enriched+=1
                    if not AUTO_ANALYZE or passes >= AUTO_ANALYZE_MAX: continue
                    gate=qualifier.qualify(eid,bundle)
                    if gate.get("state")!="QUALIFIED": continue
                    prediction=probability.run(event,bundle,gate,simulations=int(os.getenv("MONTE_CARLO_SAMPLES","10000")))
                    arb=arbiter.decide(event,bundle,gate,prediction)
                    if arb.get("state")=="FINAL_QUALIFIED" and prediction.get("selection"):
                        sel=prediction["selection"]
                        stable=hashlib.sha256((str(eid)+"|"+str(sel["market"])+"|"+str(sel["selection"])+"|UMIOS-TITAN-MarketSpecific-v3").encode()).hexdigest()
                        store.add_prediction(prediction_id=stable,fixture_id=eid,market=sel["market"],predicted_probability=sel["model_probability"],selection=sel["selection"],odds=sel["odds"],model_version="UMIOS-TITAN-MarketSpecific-v3",features={"expected_goals":prediction["expected_goals"],"history":prediction["history"],"edge":sel["edge"],"expected_value":sel["expected_value"],"simulations":prediction["simulations"],"form_trend":prediction.get("form_trend")})
                        passes+=1; state["arbiter_passes"]=state.get("arbiter_passes",0)+1; state["last_auto_analyze_at"]=time.time()
                    elif prediction.get("state")=="QUALIFIED_PREDICTION":
                        blocks+=1; state["arbiter_blocks"]=state.get("arbiter_blocks",0)+1
                except Exception as exc:
                    logger.warning("ENRICH_FAILED event=%s error=%r",eid,exc)
            state["enrichment_items"]=enriched; state["auto_analyze_items"]=passes; state["last_enrichment_at"]=time.time()
        except Exception as exc:
            logger.error("ENRICHMENT_LOOP_FAILED error=%r",exc)
        await asyncio.sleep(ENRICH_SECONDS)
@asynccontextmanager
async def lifespan(app):
    tasks=[asyncio.create_task(x()) for x in (polling_loop,evolution_loop,research_loop,learning_loop,source_learning_loop,verification_loop,enrichment_loop)];yield
    for t in tasks:t.cancel()
    await asyncio.gather(*tasks,return_exceptions=True);await adapter.close()
app=FastAPI(title="Elite MatchMaster Feed Fusion Acquisition Agent",lifespan=lifespan)
def telemetry_payload():
    now=time.time();age=None if state["last_success"] is None else round(now-state["last_success"],1);fresh_enough=state["last_success"] is not None and age<=STALE_AFTER
    return {"service":"feed-fusion-acquisition-agent","source":state["active_source"] or adapter.active_source,"running":state["running"],"poll_interval_seconds":POLL_SECONDS,"stale_after_seconds":STALE_AFTER,"last_success_age_seconds":age,"data_fresh":fresh_enough,"poller":dict(state),"fusion":dict(adapter.metrics),"scores24":dict(adapter.scores24.metrics),"evolution":evolution.status(),"learning":{"running":state["learning_running"],"prediction_count":store.prediction_count(),"resolved_count":store.resolved_prediction_count(),"performance":store.performance_summary()},"source_learning":{"running":state["source_learning_running"],"min_samples":SOURCE_MIN_SAMPLES,"scores":source_learning.status()},"verification_learning":{"running":state["verification_learning_running"],"min_sources":VERIFICATION_MIN_SOURCES,"last_run_at":state["last_verification_learning_at"]},"enrichment":{"running":state["enrichment_running"],"interval_seconds":ENRICH_SECONDS,"max_fixtures":ENRICH_MAX_FIXTURES,"last_run_at":state["last_enrichment_at"],"items":state["enrichment_items"],"auto_analyze":AUTO_ANALYZE,"auto_analyze_items":state.get("auto_analyze_items",0),"last_auto_analyze_at":state.get("last_auto_analyze_at"),"arbiter_passes":state.get("arbiter_passes",0),"arbiter_blocks":state.get("arbiter_blocks",0)},"odds_intelligence":odds.status(),"generated_at":now}
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
    for p in item.predictions:store.add_prediction(prediction_id=p.prediction_id,fixture_id=p.fixture_id,market=p.market, predicted_probability=p.predicted_probability,selection=p.selection,odds=p.odds,model_version=p.model_version,features=p.features)
    return {"ok":True,"source":"umios","recorded":len(item.predictions),"prediction_ids":[p.prediction_id for p in item.predictions]}
@app.post("/predictions/{prediction_id}/outcome")
async def record_outcome(prediction_id:str,item:OutcomeIn):store.record_outcome(prediction_id,item.outcome);return {"ok":True,"prediction_id":prediction_id,"outcome":item.outcome}
@app.get("/learning")
async def learning_status():return {"agent":"Closed-Loop Learning Core","prediction_count":store.prediction_count(),"resolved_count":store.resolved_prediction_count(),"performance":store.performance_summary(),"scores24":store.external_summary("scores24"),"evolution":evolution.status()}
@app.post("/learning/run")
async def learning_run():return learning.run(reason="manual")
@app.get("/learning/performance")
async def learning_performance():return store.performance_summary()
@app.get("/learning/sources")
async def learning_sources():return {"agent":"Source Reliability Agent","min_samples":SOURCE_MIN_SAMPLES,"scores":source_learning.status()}
@app.post("/learning/sources/run")
async def learning_sources_run():return source_learning.run()
@app.get("/learning/verify")
async def learning_verify():return {"agent":"Independent Result Verification Agent","required_sources":VERIFICATION_MIN_SOURCES,"running":state["verification_learning_running"],"last_run_at":state["last_verification_learning_at"]}
@app.post("/learning/verify/run")
async def learning_verify_run():return verification_learning.run()
@app.get("/odds")
async def odds_status():return odds.status()
@app.get("/sources/scores24")
async def scores24_status():return {"source":"scores24","url":adapter.scores24.URL,"methodology":adapter.scores24.METHODOLOGY,"metrics":adapter.scores24.metrics,"stored":store.external_summary("scores24")}
@app.get("/analyze/fixture/{event_id}")
async def analyze_fixture(event_id:str):
    bundle=await acquisition.acquire(event_id)
    event=bundle.get("event") or {}
    if event and store.get_current(event_id) is None:
        try: store.put(event_id,time.time(),adapter.payload_hash(event),event)
        except Exception as exc: logger.warning("ANALYSIS_CACHE_WRITE_FAILED event=%s error=%r",event_id,exc)
    gate=qualifier.qualify(event_id,bundle)
    analysis=core.analyze(event_id,bundle,gate)
    prediction=probability.run(event,bundle,gate,simulations=int(os.getenv("MONTE_CARLO_SAMPLES","10000")))
    arbiter_decision=arbiter.decide(event,bundle,gate,prediction)
    if arbiter_decision.get("state")=="FINAL_QUALIFIED" and prediction.get("selection"):
        sel=prediction["selection"]
        stable=hashlib.sha256((str(event_id)+"|"+str(sel["market"])+"|"+str(sel["selection"])+"|UMIOS-TITAN-MarketSpecific-v3").encode()).hexdigest()
        store.add_prediction(prediction_id=stable,fixture_id=event_id,market=sel["market"],predicted_probability=sel["model_probability"],selection=sel["selection"],odds=sel["odds"],model_version="UMIOS-TITAN-MarketSpecific-v3",features={"expected_goals":prediction["expected_goals"],"history":prediction["history"],"edge":sel["edge"],"expected_value":sel["expected_value"],"simulations":prediction["simulations"],"form_trend":prediction.get("form_trend")})
    return {"engine":"Elite MatchMaster UMIOS TITAN","fixture_id":event_id,"qualification":gate,"analysis":analysis,"prediction":prediction,"arbiter":arbiter_decision,"evidence":bundle if gate["state"]=="QUALIFIED" else {"event":bundle.get("event"),"odds":bundle.get("odds"),"verification":bundle.get("verification"),"retrieved_at":bundle.get("retrieved_at")},"prediction_status":arbiter_decision.get("state","NO_BET"),"generated_at":time.time()}

class MatchGatewayIn(BaseModel):
    home: str
    away: str
    event_id: str | None = None

def _normalize_team_name(value: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

def _resolve_today_fixture(events, home: str, away: str):
    target_home=_normalize_team_name(home)
    target_away=_normalize_team_name(away)
    exact=[]
    partial=[]
    for event in events or []:
        eh=_normalize_team_name((event.get("homeTeam") or {}).get("name",""))
        ea=_normalize_team_name((event.get("awayTeam") or {}).get("name",""))
        if eh==target_home and ea==target_away:
            exact.append(event)
        elif ((target_home in eh or eh in target_home) and
              (target_away in ea or ea in target_away)):
            partial.append(event)
    matches=exact or partial
    if not matches:
        return None
    matches.sort(key=lambda e: float(e.get("startTimestamp") or e.get("timestamp") or 0))
    return matches[0]

async def _run_fixture_analysis(event_id: str):
    bundle=await acquisition.acquire(event_id)
    event=bundle.get("event") or {}
    if event and store.get_current(event_id) is None:
        try:
            store.put(event_id,time.time(),adapter.payload_hash(event),event)
        except Exception as exc:
            logger.warning("ANALYSIS_CACHE_WRITE_FAILED event=%s error=%r",event_id,exc)
    gate=qualifier.qualify(event_id,bundle)
    analysis=core.analyze(event_id,bundle,gate)
    prediction=probability.run(event,bundle,gate,simulations=int(os.getenv("MONTE_CARLO_SAMPLES","10000")))
    arbiter_decision=arbiter.decide(event,bundle,gate,prediction)
    if arbiter_decision.get("state")=="FINAL_QUALIFIED" and prediction.get("selection"):
        sel=prediction["selection"]
        stable=hashlib.sha256((str(event_id)+"|"+str(sel["market"])+"|"+str(sel["selection"])+"|UMIOS-TITAN-MarketSpecific-v3").encode()).hexdigest()
        store.add_prediction(prediction_id=stable,fixture_id=event_id,market=sel["market"],predicted_probability=sel["model_probability"],selection=sel["selection"],odds=sel["odds"],model_version="UMIOS-TITAN-MarketSpecific-v3",features={"expected_goals":prediction["expected_goals"],"history":prediction["history"],"edge":sel["edge"],"expected_value":sel["expected_value"],"simulations":prediction["simulations"],"form_trend":prediction.get("form_trend")})
    return {"engine":"Elite MatchMaster UMIOS TITAN","fixture_id":event_id,"qualification":gate,"analysis":analysis,"prediction":prediction,"arbiter":arbiter_decision,"evidence":bundle if gate["state"]=="QUALIFIED" else {"event":bundle.get("event"),"odds":bundle.get("odds"),"verification":bundle.get("verification"),"retrieved_at":bundle.get("retrieved_at")},"prediction_status":arbiter_decision.get("state","NO_BET"),"generated_at":time.time()}

@app.post("/analyze/match")
async def analyze_match_gateway(item: MatchGatewayIn):
    if not item.home.strip() or not item.away.strip():
        raise HTTPException(400,"home and away are required")
    if item.event_id:
        return await _run_fixture_analysis(item.event_id)
    data=await adapter.today_events()
    event=_resolve_today_fixture(data.get("events",[]),item.home,item.away)
    if not event:
        raise HTTPException(404,f"Today's fixture not found: {item.home} vs {item.away}")
    return await _run_fixture_analysis(str(event.get("id")))

@app.get("/analyze/match")
async def analyze_match_gateway_get(home: str, away: str, event_id: str | None = None):
    return await analyze_match_gateway(MatchGatewayIn(home=home,away=away,event_id=event_id))

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
