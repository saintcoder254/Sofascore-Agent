# Elite MatchMaster SofaScore Acquisition Agent

FastAPI acquisition service for Elite MatchMaster. It polls SofaScore's public football API on a configurable interval (default 60 seconds), caches event snapshots, applies freshness/conflict checks, and exposes telemetry for verification.

## Verification telemetry
- `GET /health` — service + ingestion health
- `GET /status` — full poller/source telemetry
- `GET /telemetry` — explicit ingestion verification endpoint
- `GET /fusion/feed` — freshness-gated MatchMaster feed plus telemetry
- `POST /poll` — immediate acquisition test

Telemetry records poll count, successful/failed polls, consecutive failures, event counts, timestamps, HTTP status, request count, latency, last endpoint, and whether the latest successful acquisition is still fresh.

## Local
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Default poll interval is 60 seconds. Override with `POLL_SECONDS`. Default stale threshold is 180 seconds (`STALE_AFTER_SECONDS`).
