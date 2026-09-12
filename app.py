import asyncio, os, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from sofascore_adapter import SofaScoreAdapter
from integrity import FreshnessGate, ConflictGate
from store import Store

POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
STALE_AFTER = int(os.getenv("STALE_AFTER_SECONDS", "180"))
BASE = os.getenv("SOFASCORE_BASE", "https://www.sofascore.com/api/v1")
DB = os.getenv("DATABASE_PATH", "matchmaster.db")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))

adapter = SofaScoreAdapter(BASE, TIMEOUT)
store = Store(DB)
fresh = FreshnessGate(STALE_AFTER)
conflict = ConflictGate()
state = {"last_poll": None, "last_success": None, "last_error": None,
         "items": 0, "running": False}

async def poll_once():
    state["last_poll"] = time.time()
    try:
        data = await adapter.today_events()
        events = data.get("events", [])
        for event in events:
            eid = str(event.get("id", ""))
            if not eid:
                continue
            prev = store.get_current(eid)
            payload_hash = adapter.payload_hash(event)
            conflict.compare(prev["payload"] if prev else None, event)
            store.put(eid, time.time(), payload_hash, event)
        state["items"] = len(events)
        state["last_success"] = time.time()
        state["last_error"] = None
        return len(events)
    except Exception as exc:
        state["last_error"] = repr(exc)
        raise

async def polling_loop():
    state["running"] = True
    backoff = POLL_SECONDS
    while True:
        try:
            await poll_once()
            backoff = POLL_SECONDS
        except Exception:
            backoff = min(max(POLL_SECONDS, backoff * 2), 900)
        await asyncio.sleep(backoff)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(polling_loop())
    yield
    task.cancel()
    await adapter.close()

app = FastAPI(title="Elite MatchMaster SofaScore Acquisition Agent", lifespan=lifespan)

@app.get("/health")
async def health():
    ok = state["last_success"] is not None and (
        time.time() - state["last_success"] <= STALE_AFTER * 2)
    return {"ok": ok, "service": "sofascore-acquisition-agent",
            "poll_seconds": POLL_SECONDS, "state": state}

@app.get("/status")
async def status():
    return state

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
    return {"fixture_id": event_id,
            "integrity": {"status": status, "age_seconds": age, "reason": reason},
            "data": row}

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
        return {"ok": True, "items": count, "retrieved_at": time.time()}
    except Exception as exc:
        raise HTTPException(502, str(exc))

@app.get("/fusion/feed")
async def fusion_feed():
    output = []
    for row in store.current():
        status, age, reason = fresh.evaluate(row["retrieved_at"])
        output.append({
            "fixture_id": row["fixture_id"],
            "eligible": status == "FRESH",
            "integrity_status": status,
            "age_seconds": age,
            "reason": reason,
            "data": row["payload"] if status == "FRESH" else None
        })
    return {"source": "sofascore", "generated_at": time.time(), "items": output}
