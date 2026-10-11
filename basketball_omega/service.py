"""Standalone basketball service surface.

This can be deployed independently of the football FastAPI application.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from basketball_omega.contracts import BasketballContext
from basketball_omega.router import BasketballRouter

app = FastAPI(title="Elite MatchMaster Basketball OMEGA", version="1.1")
router = BasketballRouter()

class BasketballRequest(BaseModel):
    home: str
    away: str
    history: list[dict] = Field(default_factory=list)
    team_stats: dict[str, dict[str, float]] = Field(default_factory=dict)
    players: dict[str, dict] = Field(default_factory=dict)
    injuries: dict[str, dict] = Field(default_factory=dict)
    lineups: dict[str, list[dict]] = Field(default_factory=dict)
    market: dict = Field(default_factory=dict)

@app.get("/health")
def health():
    return {"ok": True, "service": "basketball-omega", "sport": "basketball"}

@app.post("/analyze")
def analyze(item: BasketballRequest):
    if not item.home.strip() or not item.away.strip():
        raise HTTPException(400, "home and away are required")
    ctx = BasketballContext(
        home=item.home, away=item.away, history=item.history,
        team_stats=item.team_stats, players=item.players, injuries=item.injuries,
        lineups=item.lineups, market=item.market,
    )
    verdict = router.analyze(ctx)
    return {
        "engine": "Elite MatchMaster Basketball OMEGA",
        "sport": "basketball",
        "verdict": verdict,
    }
