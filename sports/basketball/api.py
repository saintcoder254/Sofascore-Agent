from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from pydantic import BaseModel

from .analysis_memory import BasketballAnalysisMemoryGate
from .historical_memory import BasketballHistoricalMemory
from .market_service import BasketballMarketService
from .market_store import BasketballMarketStore
from .service import BasketballDataService

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
historical_memory = BasketballHistoricalMemory(
    os.getenv("BASKETBALL_MEMORY_DB", os.getenv("BASKETBALL_MARKET_DB", "basketball_titan.db")),
    os.getenv("BASKETBALL_HISTORICAL_DATASET", "data/basketball/pregame.jsonl"),
)
analysis_memory_gate = BasketballAnalysisMemoryGate(historical_memory)
_tasks: list[asyncio.Task] = []


class HistoricalContextRequest(BaseModel):
    cutoff_timestamp: float
    fixture_id: str | None = None
    home_team_id: str | None = None
    away_team_id: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    raw_limit: int = 250
    market_limit: int = 500
    verified_limit: int = 250



class AnalysisMemoryRequest(HistoricalContextRequest):
    """Memory gate request used by downstream basketball analysis."""

    pass


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
        "version": "basketball-titan-1.2-risk-gated",
        "odds_api_configured": bool(os.getenv("THE_ODDS_API_KEY")),
        "primary_source": os.getenv("BASKETBALL_PRIMARY_SOURCE", "sofascore"),
        "verify_source": os.getenv("BASKETBALL_VERIFY_SOURCE", "espn"),
        "historical_memory": True,
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


@app.post("/memory/context")
async def memory_context(request: HistoricalContextRequest):
    bundle = analysis_memory_gate.query(**request.model_dump())
    return bundle.as_dict()


@app.post("/analysis/memory")
async def analysis_memory(request: AnalysisMemoryRequest):
    """Mandatory historical-memory query boundary for downstream analysis.

    Call this boundary before feature engineering/modeling. The returned context
    is cutoff-safe and explicitly marks that the memory query was performed.
    """
    bundle = analysis_memory_gate.query(**request.model_dump())
    return bundle.as_dict()
