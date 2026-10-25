# Elite MatchMaster SofaScore Acquisition Agent

Continuous football data acquisition and pre-analysis qualification service for Elite MatchMaster UMIOS TITAN.

## Acquisition pipeline

The service polls the primary SofaScore feed every 60 seconds by default and uses ESPN/FotMob as fallback sources, with Futbol24 and Scores24 verification. Event snapshots are persisted to the configured database.

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

The application uses `DATABASE_PATH` for its SQLite database (default: `matchmaster.db`) and `CASE_DATABASE_DIR` for fixture case files (default: `case_databases`). Configure these paths for the runtime environment and mount persistent storage where durable history is required. Without persistent storage, local database files may not survive instance replacement or redeployment.

## Scheduled execution on Vercel

Vercel does not keep the application's in-process polling and learning loops alive. The
GitHub Actions workflow at `.github/workflows/matchmaster-scheduler.yml` invokes
authenticated one-shot stages instead:

- Every 5 minutes: poll fixtures, enrich/analyze a bounded fixture set, run learning,
  score sources, and verify results.
- Every 6 hours: run evolution and research.
- A manual workflow dispatch is available for an operator-triggered run.

Before the workflow can run, configure these values:

1. In Vercel Project Settings → Environment Variables, set `MATCHMASTER_CRON_TOKEN`
   to a long random secret (at least 32 random bytes), then redeploy.
2. In GitHub repository Settings → Secrets and variables → Actions, add
   `MATCHMASTER_CRON_TOKEN` with exactly the same value.
3. Add `MATCHMASTER_BASE_URL` as a GitHub Actions repository secret, set to the
   deployed API base URL (for example `https://sofascore-agent.vercel.app`, without a
   trailing slash).
4. Run the `MatchMaster scheduled pipeline` workflow manually once and inspect every
   stage's response and the Vercel function logs. Then confirm `/health`, `/status`,
   and `/learning/omega/oos` after a real settled fixture is recorded.

The `POST /cron/run/{stage}` endpoint requires `Authorization: Bearer <token>` and
returns 503 if the Vercel token is missing or 401 for an invalid token. Never place the
token in a URL, source file, workflow YAML, or logs.

**Persistence limitation:** this scheduler does not make SQLite durable. The default
`matchmaster.db` and per-fixture files in `case_databases` can be lost when Vercel
replaces an instance, and separate serverless instances may not share their local files.
Do not mark operational correctness as passed until durable shared storage is configured
and a redeploy-retention test proves that predictions, outcomes, odds snapshots, and
case audit chains survive. The scheduled workflow is also not active until the required
secrets are configured.

## Local

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Default poll interval is 60 seconds. Override with POLL_SECONDS. Default stale threshold is 180 seconds (STALE_AFTER_SECONDS).

## UMIOS TITAN core analysis

The service now includes a bounded continuous enrichment loop for today's fixtures. It refreshes the nearest eligible fixtures every 300 seconds by default, collecting the canonical event, statistics, shotmap, incidents, lineups, and odds evidence. Configuration is controlled by ENRICH_SECONDS and ENRICH_MAX_FIXTURES.

The /analyze/fixture/{event_id} endpoint passes a qualified evidence bundle into umios_core.py. The core normalizes numeric/statistical evidence, groups available odds into supported market families, de-vigs market-implied probabilities, and exposes a conservative candidate set. It deliberately labels these as BENCHMARK_ONLY until an independently trained probability model is connected; market odds are not treated as a model prediction.


## Market-specific probability layer

UMIOS TITAN now uses `umios_market_models.py` as a specialist probability layer rather than treating every market as a generic goal model.

- 1X2, double chance, DNB, BTTS, totals, and correct score are derived from an independent score-distribution model.
- Corners are modeled only when identifiable corner statistics are present.
- Cards are modeled only when identifiable card/booking incidents provide enough observations.
- Each market carries its own evidence availability and confidence metadata.
- The final arbiter blocks corners/cards when their required evidence is unavailable.
- The existing Monte Carlo ensemble, form trend, odds de-vigging, edge/EV gates, calibration, and adversarial checks remain active.
- Unsupported or evidence-thin markets remain `NO_BET`; the system does not manufacture probabilities.

This architecture separates market generation from final qualification: a market must have both a model probability and sufficient evidence before it can become a persisted prediction.


## Basketball hardening — UMIOS TITAN v2

Basketball is now routed away from the legacy football Poisson-goals probability layer. The dedicated `basketball_probability_engine.py` uses point-level offensive/defensive evidence, empirical variance and correlated Monte Carlo scoring scenarios. Total-points probabilities are evaluated at the exact bookmaker line.

The basketball path requires a minimum evidence sample, applies the competition-regime gate, and feeds simulated totals into the existing Basketball Volatility Guard. The guard now detects basketball even when the upstream event omits explicit sport metadata by using a structural TOTAL_POINTS signature.

The hardening layer also includes:
- `competition_regime_agent.py` for youth/reserve/friendly volatility restrictions.
- `titan_incident_audit.py` for post-incident replay diagnostics and overconfidence detection.
- `tests/` regression coverage for basketball routing, thin-history NO_BET behavior, guard applicability and audit logic.
- `GET /audit/incidents` for persisted outcome diagnostics.
- `docs/UMIOS_TITAN_10_POINT_HARDENING.md` documenting the ten corrective controls.

The model deliberately prefers NO_BET when the probability model, evidence regime or sample depth is inadequate. Monte Carlo sample count is a simulation parameter, not a substitute for correct model specification.
