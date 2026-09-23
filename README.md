# Elite MatchMaster SofaScore Acquisition Agent

Continuous football data acquisition and pre-analysis qualification service for Elite MatchMaster UMIOS TITAN.

## Acquisition pipeline

The service polls the primary SofaScore feed every 60 seconds by default and uses ESPN/FotMob as fallback sources, with Futbol24 and Scores24 verification. Event snapshots are persisted to the Render-mounted database.

For a requested fixture, the enriched acquisition engine pulls:
- canonical event/status/venue identity
- lineups and available lineup signals
- event statistics
- shotmap
- incidents
- current event odds where the provider exposes them
- independent verification data

The UMIOS qualification gate then checks feed freshness, fixture identity, match state, required evidence availability, lineup signal, external verification, and market availability. A blocked fixture is explicitly returned as NO_BET; the system does not manufacture missing probabilities.

## UMIOS analysis endpoint

GET /analyze/fixture/{event_id}

This endpoint acquires the fixture evidence bundle, persists the canonical event when necessary, applies the UMIOS integrity gate, and returns either:

- READY_FOR_CORE_MODEL — evidence passed the acquisition/qualification gate.
- NO_BET — evidence is stale, incomplete, conflicting, or otherwise unsuitable for prediction.

The endpoint is deliberately a gate: a qualifying data bundle must reach the downstream UMIOS model before a market prediction is allowed.

## Verification telemetry

- GET /health — service + ingestion health
- GET /status — full poller/source telemetry
- GET /telemetry — explicit ingestion verification endpoint
- GET /fusion/feed — freshness-gated MatchMaster feed
- POST /poll — immediate acquisition test
- GET /analyze/fixture/{event_id} — enriched fixture acquisition + UMIOS qualification

Telemetry records poll count, source success/failure, freshness, request latency, verification activity, learning cycles, and odds/source intelligence.

## Persistent storage

Render mounts /data as persistent storage and the application uses /data/matchmaster.db. This keeps snapshots, predictions, outcomes, external observations, source scores, and learning history across deploys.

## Local

pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000

Default poll interval is 60 seconds. Override with POLL_SECONDS. Default stale threshold is 180 seconds (STALE_AFTER_SECONDS).