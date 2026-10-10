# Elite MatchMaster SofaScore Acquisition Agent

Football and basketball evidence acquisition, model evaluation, audit persistence, and conservative betting qualification for Elite MatchMaster UMIOS TITAN.

## Operating modes and limits

**GitHub Actions is the mandatory code-validation gate.** The `omega-ci` and `UMIOS TITAN regression` workflows compile the Python project and run its unit/regression tests. A green CI run confirms only the checks those workflows actually execute; it does not prove live sports-data provider availability, continuous API uptime, or fixture-specific execution.

This repository does not depend on Render. GitHub Actions is not a continuously running API host. Workflow runs have platform usage limits, and any scheduled job must remain bounded and must not be treated as an always-on service.

## Acquisition pipeline

The acquisition layer tries SofaScore first, falls back to ESPN/FotMob for supported event discovery, and uses Futbol24/Scores24 as verification sources where available. Detailed event enrichment currently relies on the SofaScore event endpoints; an alternate scoreboard source is not equivalent to complete event statistics, lineups, shot maps, history, and odds.

Provider responses can be blocked, rate-limited, empty, stale, or incomplete. These cases must be visible as source errors and qualification blockers. The system must not infer missing evidence or claim a source was verified when it was not.

For a requested fixture, the acquisition engine attempts to collect:
- canonical event identity and match status
- lineups and available lineup signals
- event statistics, shot map, and incidents
- head-to-head and recent team history
- event odds when exposed by a provider
- independent verification observations

## Mandatory fixture decision gate

The qualification and decision pipeline is fail-closed:

1. Acquire the fixture-specific evidence bundle.
2. Check fixture identity, match state, freshness, completeness, market availability, and independent verification.
3. Run the applicable sport/market probability engine and simulation only when its prerequisites are satisfied.
4. Run specialist, market-value, calibration/consensus, historical-failure, and adversarial gates.
5. Persist the evidence and decision trace to the case audit database.
6. Return a qualified verdict only if every mandatory gate passes. Otherwise return `NO_BET` or `BLOCKED` with explicit reasons.

A settled result or screenshot by itself is not a substitute for the stored pre-match evidence, prediction, odds, and execution trace. Retrospective audits must label missing records as unavailable rather than reconstructing them as if they had been observed.

## API endpoints (when the application is run by an operator)

- `GET /health` — service and ingestion freshness
- `GET /status` and `GET /telemetry` — poller/source telemetry
- `GET /fusion/feed` — freshness-gated feed
- `POST /poll` — immediate acquisition attempt
- `GET /analyze/fixture/{event_id}` — acquisition, qualification, probability analysis, and arbiter
- `GET /analyze/match?home=...&away=...` — resolve a current-day fixture by team names
- `GET /case/{fixture_id}/audit` — fixture audit-chain events
- `GET /case/{fixture_id}/trust` — latest data-trust envelope and audit-chain status

The fixture analysis endpoints require live provider access. GitHub Actions tests do not call those endpoints against live providers unless a dedicated integration test explicitly says so.

## Local execution

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Default polling interval is 60 seconds and default stale threshold is 180 seconds. Configure with `POLL_SECONDS` and `STALE_AFTER_SECONDS`. To keep resource use bounded, enrichment and automatic analysis are conservatively disabled/reduced by default in the hardened configuration; enabling them should be an explicit operator decision.

## Probability and market integrity

The market-specific probability layer distinguishes 1X2, double chance, draw-no-bet, BTTS, totals, correct score, corners, cards, and handicap. Market odds are a benchmark, not an independent model prediction. Unsupported or evidence-thin markets must remain `NO_BET`; corners/cards require their own evidence.

Monte Carlo output, model probabilities, expected value, and calibration claims must be tied to the actual evidence and model run. A single correct result does not prove calibration. No selection may be certified solely because it won.

## GitHub Actions validation

The pull request must pass both `omega-ci` and `UMIOS TITAN regression` before merge. The checks include Python compilation and unit/regression tests. Keep fixture-specific execution logs, provider-integration results, and model-calibration evidence distinct from CI status.

**No green checks, no merge. No verified fixture evidence or failed mandatory gate, no betting verdict.**
