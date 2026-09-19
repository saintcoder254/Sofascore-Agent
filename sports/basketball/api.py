from __future__ import annotations
import asyncio
import os
from fastapi import FastAPI
from .service import BasketballDataService
from .market_service import BasketballMarketService
from .market_store import BasketballMarketStore

app = FastAPI(title="Elite MatchMaster Basketball TITAN")

data_service = BasketballDataService(
    int(os.getenv("BASKETBALL_DATA_INTERVAL_SECONDS", "60"))
)
market_store = BasketballMarketStore(
    os.getenv("BASKETBALL_MARKET_DB", "basketball_titan.db")
)
market_service = BasketballMarketService(
    market_store,
    int(os.getenv("BASKETBALL_MARKET_INTERVAL_SECONDS", "60"))
)
_tasks: list[asyncio.Task] = []

@app.on_event("startup")
async def startup():
    _tasks.append(asyncio.create_task(data_service.run()))
    _tasks.append(asyncio.create_task(market_service.run_forever()))

@app.on_event("shutdown")
async def shutdown():
    await data_service.close()
    for task in _tasks:
        task.cancel()

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "basketball-titan",
        "version": "basketball-titan-1.1",
        "odds_api_configured": bool(os.getenv("THE_ODDS_API_KEY")),
        "primary_source": os.getenv("BASKETBALL_PRIMARY_SOURCE", "sofascore"),
        "verify_source": os.getenv("BASKETBALL_VERIFY_SOURCE", "espn"),
        "last_collection": data_service.last_result,
        "last_error": data_service.last_error,
    }

@app.post("/collect")
async def collect():
    return await data_service.collect_once()

@app.post("/markets/collect")
async def collect_markets():
    count = await market_service.collect_once()
    return {"snapshots_collected": count}
