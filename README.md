# Elite MatchMaster — SofaScore Persistent Acquisition Agent

Deployable service for continuously polling SofaScore football data and exposing a clean feed to Elite MatchMaster.

Default live polling interval: 60 seconds.
The service fails closed when cached data is stale.

## Run locally
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080

## Endpoints
GET /health
GET /status
GET /live
GET /fixture/{event_id}
GET /events/today
POST /poll
GET /fusion/feed

## Environment
POLL_SECONDS=60
STALE_AFTER_SECONDS=180
SOFASCORE_BASE=https://www.sofascore.com/api/v1
DATABASE_PATH=matchmaster.db

This package is deployable code. It is not a claim that a persistent cloud process is already running.
