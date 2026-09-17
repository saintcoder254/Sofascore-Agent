import asyncio, os, time, logging, traceback, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sofascore_adapter import SofaScoreAdapter
from integrity import FreshnessGate, ConflictGate
from store import Store
from evolution import EvolutionAgent
from research_engine import ResearchEngine

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("emm.poller")

POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
STALE_AFTER = int(os.getenv("STALE_AFTER_SECONDS", "180"))
BASE = os.getenv("SOFASCORE_BASE", "https://www.sofascore.com/api/v1")
DB = os.getenv("DATABASE_PATH", "matchmaster.db")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
EVOLUTION_SECONDS = int(os.getenv("EVOLUTION_SECONDS", "21600"))
EVOLUTION_MIN_SAMPLES = int(os.getenv("EVOLUTION_MIN_SAMPLES", "100"))
RESEARCH_SECONDS = int(os.getenv("RESEARCH_SECONDS", "21600"))

adapter = SofaScoreAdapter(BASE, TIMEOUT)
store = Store(DB)
fresh = FreshnessGate(STALE_AFTER)
conflict = ConflictGate()
evolution = EvolutionAgent(store, EVOLUTION_MIN_SAMPLES)
research = ResearchEngine(store)
state = {
    "last_poll": None, "last_success": None, "last_error": None,
    "last_poll_duration_ms": None, "last_poll_items": 0,
    "polls_total": 0, "polls_success": 0, "polls_failed": 0,
    "consecutive_failures": 0, "next_poll_at": None,
    "items": 0, "running": False,
    "evolution_running": False, "last_evolution_at": None,
    "research_running": False, "last_research_at": None,
}

class PredictionIn(BaseModel):
    prediction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fixture_id: str
    market: str
    predicted_probability: float = Field(ge=0, le=1)
    selection: str | None = None
    odds: float | None = Field(default=None, gt=1)
    model_version: str = "unknown"
    features: dict = Field(default_factory=dict)

class OutcomeIn(BaseModel):
    outcome: float = Field(ge=0, le=1)

async def poll_once():
    started = time.perf_counter()
    state["last_poll"] = time.time()
    state["polls_total"] += 1
    poll_no = state["polls_total"]
    logger.info("POLL_START number=%s source=sofascore interval_seconds=%s", poll_no, POLL_SECONDS)
    try:
        data = await adapter.today_events()
        events = data.get("events", [])
        stored = 0
        skipped = 0
        for event in events:
            eid = str(event.get("id", ""))
            if not eid:
                skipped += 1
                continue
            prev = store.get_current(eid)
            payload_hash = adapter.payload_hash(event)
            conflict.compare(prev["payload"] if prev else None, event)
            store.put(eid, time.time(), payload_hash, event)
            stored += 1
        duration = round((time.perf_counter() - started) * 1000, 1)
        state.update({"items": len(events), "last_poll_items": stored, "last_success": time.time(), "last_error": None, "last_poll_duration_ms": duration, "polls_success": state["polls_success"] + 1, "consecutive_failures": 0})
        logger.info("POLL_SUCCESS number=%s http_status=%s events=%s stored=%s skipped=%s duration_ms=%s retrieved_at=%.3f", poll_no, adapter.metrics.get("last_status_code"), len(events), stored, skipped, duration, state["last_success"])
        return len(events)
    except Exception as exc:
        duration = round((time.perf_counter() - started) * 1000, 1)
        state["last_error"] = repr(exc)
        state["last_poll_duration_ms"] = duration
        state["polls_failed"] += 1
        state["consecutive_failures"] += 1
        logger.error("POLL_FAILED number=%s duration_ms=%s consecutive_failures=%s error=%r", poll_no, duration, state["consecutive_failures"], exc)
        logger.debug(traceback.format_exc())
        raise

async def polling_loop():
    state["running"] = True
    backoff = POLL_SECONDS
    logger.info("POLL_LOOP_STARTED interval_seconds=%s stale_after_seconds=%s", POLL_SECONDS, STALE_AFTER)
    while True:
        try:
            count = await poll_once()
            backoff = POLL_SECONDS
            state["next_poll_at"] = time.time() + backoff
            logger.info("POLL_SCHEDULED next_in_seconds=%s items=%s", backoff, count)
        except Exception:
            backoff = min(max(POLL_SECONDS, backoff * 2), 900)
            state["next_poll_at"] = time.time() + backoff
            logger.warning("POLL_BACKOFF next_in_seconds=%s", backoff)
        await asyncio.sleep(backoff)

async def evolution_loop():
    state["evolution_running"] = True
    logger.info("EVOLUTION_LOOP_STARTED interval_seconds=%s min_samples=%s", EVOLUTION_SECONDS, EVOLUTION_MIN_SAMPLES)
    while True:
        try:
            result = evolution.run_cycle(reason="scheduled")
            state["last_evolution_at"] = result["created_at"]
            logger.info("EVOLUTION_CYCLE status=%s samples=%s candidates=%s", result["status"], result["baseline"]["samples"], len(result["candidates"]))
        except Exception as exc:
            logger.error("EVOLUTION_CYCLE_FAILED error=%r", exc)
        await asyncio.sleep(EVOLUTION_SECONDS)

async def research_loop():
    state["research_running"] = True
    logger.info("RESEARCH_LOOP_STARTED interval_seconds=%s", RESEARCH_SECONDS)
    while True:
        try:
            report = research.research_report()
            state["last_research_at"] = report["generated_at"]
            logger.info("RESEARCH_CYCLE hypotheses=%s features=%s technology=%s walk_forward=%s", len(report["hypotheses"]), len(report["feature_inventory"]), len(report["technology"]), report["walk_forward"].get("status"))
        except Exception as exc:
            logger.error("RESEARCH_CYCLE_FAILED error=%r", exc)
        await asyncio.sleep(RESEARCH_SECONDS)

@asynccontextmanager
async def lifespan(app):
    poll_task = asyncio.create_task(polling_loop())
    evolution_task = asyncio.create_task(evolution_loop())
    research_task = asyncio.create_task(research_loop())
    yield
    for task in (poll_task, evolution_task, research_task):
        task.cancel()
    state["running"] = False
    state["evolution_running"] = False
    state["research_running"] = False
    await asyncio.gather(poll_task, evolution_task, research_task, return_exceptions=True)
    await adapter.close()

app = FastAPI(title="Elite MatchMaster SofaScore Acquisition Agent", lifespan=lifespan)

def telemetry_payload():
    now = time.time()
    last_success = state["last_success"]
    age = None if last_success is None else round(now - last_success, 1)
    fresh_enough = last_success is not None and age <= STALE_AFTER
    return {"service": "sofascore-acquisition-agent", "source": "sofascore", "running": state["running"], "poll_interval_seconds": POLL_SECONDS, "stale_after_seconds": STALE_AFTER, "last_success_age_seconds": age, "data_fresh": fresh_enough, "ingestion_verified": bool(fresh_enough and state["polls_success"] > 0 and adapter.metrics["requests_success"] > 0), "poller": dict(state), "http": dict(adapter.metrics), "evolution": evolution.status(), "research": {"running": state["research_running"], "last_research_at": state["last_research_at"], "interval_seconds": RESEARCH_SECONDS}, "generated_at": now}

@app.get("/health")
async def health():
    t = telemetry_payload()
    return {"ok": t["data_fresh"], **t}

@app.get("/status")
async def status():
    return telemetry_payload()

@app.get("/telemetry")
async def telemetry():
    return telemetry_payload()

@app.get("/evolution")
async def evolution_status():
    return evolution.status()

@app.post("/evolution/run")
async def evolution_run():
    try:
        return evolution.run_cycle(reason="manual")
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/research")
async def research_status():
    return research.research_report()

@app.post("/research/run")
async def research_run():
    try:
        return research.research_report()
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/predictions")
async def record_prediction(item: PredictionIn):
    store.add_prediction(prediction_id=item.prediction_id, fixture_id=item.fixture_id, market=item.market, predicted_probability=item.predicted_probability, selection=item.selection, odds=item.odds, model_version=item.model_version, features=item.features)
    return {"ok": True, "prediction_id": item.prediction_id}

@app.post("/predictions/{prediction_id}/outcome")
async def record_outcome(prediction_id: str, item: OutcomeIn):
    store.record_outcome(prediction_id, item.outcome)
    return {"ok": True, "prediction_id": prediction_id, "outcome": item.outcome}

@app.get("/live")
async def live():
    rows = store.current()
    return {"count": len(rows), "items": rows}

@app.get("/fixture/{event_id}")
async def fixture(event_id: str):
    row = store.get_current(event_id)
    if not row:
        raise HTTPException(404, "fixture not cached")
    status, age, reason = fresh.evaluate(row["retrieved_at"])
    return {"fixture_id": event_id, "integrity": {"status": status, "age_seconds": age, "reason": reason}, "data": row}

@app.get("/events/today")
async def events_today():
    try:
        return await adapter.today_events()
    except Exception as exc:
        raise HTTPException(502, str(exc))

@app.post("/poll")
async def manual_poll():
    try:
        count = await poll_once()
        return {"ok": True, "items": count, "retrieved_at": time.time(), "telemetry": telemetry_payload()}
    except Exception as exc:
        raise HTTPException(502, str(exc))

@app.get("/fusion/feed")
async def fusion_feed():
    output = []
    for row in store.current():
        status, age, reason = fresh.evaluate(row["retrieved_at"])
        output.append({"fixture_id": row["fixture_id"], "eligible": status == "FRESH", "integrity_status": status, "age_seconds": age, "reason": reason, "data": row["payload"] if status == "FRESH" else None})
    return {"source": "sofascore", "generated_at": time.time(), "telemetry": telemetry_payload(), "items": output}
