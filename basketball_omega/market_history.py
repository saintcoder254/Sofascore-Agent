"""Timestamped historical-market acquisition and normalization contracts.

The adapter is deliberately credential-driven: no API key is stored in Git.
It consumes point-in-time snapshots and emits immutable MarketTick records.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os

@dataclass(frozen=True)
class MarketTick:
    fixture_id: str
    market: str
    side: str
    line: float | None
    price: float | None
    bookmaker: str
    captured_at: float
    effective_at: float | None
    source: str

def parse_ts(value):
    if value is None: return None
    if isinstance(value,(int,float)): return float(value)
    s=str(value).replace("Z","+00:00")
    return datetime.fromisoformat(s).timestamp()

class TheOddsAPIHistoricalAdapter:
    """Parse The Odds API historical snapshots without embedding credentials."""
    BASE="https://api.the-odds-api.com/v4/historical/sports/basketball_nba/events"

    def __init__(self, api_key=None, request_get=None):
        self.api_key=api_key or os.getenv("THE_ODDS_API_KEY")
        self.request_get=request_get

    @property
    def configured(self):
        return bool(self.api_key and self.request_get)

    def fetch_event_snapshot(self,event_id,date_iso,markets=("spreads","totals"),regions="us"):
        if not self.configured: raise RuntimeError("historical_market_source_not_configured")
        response=self.request_get(self.BASE+"/"+str(event_id)+"/odds",params={
            "apiKey":self.api_key,"regions":regions,"markets":",".join(markets),
            "date":date_iso,"dateFormat":"iso","oddsFormat":"american"})
        response.raise_for_status()
        return response.json()

    def normalize_snapshot(self,payload):
        fixture_id=str(payload["data"]["id"])
        captured=parse_ts(payload.get("timestamp"))
        ticks=[]
        for book in payload["data"].get("bookmakers",[]):
            bookmaker=str(book.get("key",""))
            effective=parse_ts(book.get("last_update")) or captured
            for market in book.get("markets",[]):
                key=str(market.get("key",""))
                if key=="spreads": market_name="spread"
                elif key=="totals": market_name="total"
                else: continue
                for outcome in market.get("outcomes",[]):
                    ticks.append(MarketTick(
                        fixture_id,market_name,str(outcome.get("name","")),
                        float(outcome["point"]) if outcome.get("point") is not None else None,
                        float(outcome["price"]) if outcome.get("price") is not None else None,
                        bookmaker,captured,effective,"the_odds_api"))
        return tuple(ticks)

def select_snapshot_at_or_before(ticks, cutoff_at, bookmaker=None, market=None, side=None):
    eligible=[t for t in ticks if t.captured_at <= float(cutoff_at)]
    if bookmaker is not None: eligible=[t for t in eligible if t.bookmaker==bookmaker]
    if market is not None: eligible=[t for t in eligible if t.market==market]
    if side is not None: eligible=[t for t in eligible if t.side==side]
    return max(eligible,key=lambda t:t.captured_at) if eligible else None

def verified_close(ticks,event_at,entry_at,bookmaker=None,market=None,side=None):
    eligible=[t for t in ticks if float(entry_at) <= t.captured_at <= float(event_at)]
    if bookmaker is not None: eligible=[t for t in eligible if t.bookmaker==bookmaker]
    if market is not None: eligible=[t for t in eligible if t.market==market]
    if side is not None: eligible=[t for t in eligible if t.side==side]
    return max(eligible,key=lambda t:t.captured_at) if eligible else None

def consensus_line(ticks, captured_at, market, side, min_books=2):
    rows=[t.line for t in ticks if t.market==market and t.side==side and t.captured_at==captured_at and t.line is not None]
    if len(rows)<int(min_books): return None
    rows=sorted(rows)
    n=len(rows); mid=n//2
    return rows[mid] if n%2 else (rows[mid-1]+rows[mid])/2.0