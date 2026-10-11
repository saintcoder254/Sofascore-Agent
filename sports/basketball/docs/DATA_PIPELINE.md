# Basketball TITAN — Real Data Pipeline

## Acquisition boundary
Basketball data is isolated under `sports/basketball/`. The existing football acquisition stack is not modified to pretend it is basketball-aware.

Sofascore is currently the primary acquisition source for the basketball acquisition boundary. Raw source payloads are retained for reconstruction and audit.

## Operational layers
1. Fixture layer — scheduled events, status, teams, competition, tipoff.
2. Result layer — final scores and overtime state.
3. Event layer — incidents and state transitions.
4. Lineup layer — starters, availability, expected minutes and substitutions where available.
5. Statistics layer — team/player box and advanced statistics where exposed.
6. Shot layer — shotmap and scoring profile where exposed.
7. Historical layer — prior team games and rolling windows.
8. Market layer — opening, current and closing lines.
9. Verification layer — independent confirmation before a result enters training truth.
10. Calibration layer — Brier/log-loss, calibration gap, MAE and closing-line evaluation.
11. Model-selection layer — out-of-sample performance-weighted model aggregation.

## Feature rules
Pregame models may use only information timestamped before tipoff. Live models may use event data only after the event timestamp. Any feature whose timestamp cannot be established is quarantined.

## Historical dataset contract
Every pregame row contains:
- fixture_id
- competition
- scheduled_tipoff
- snapshot_timestamp
- home/away identifiers
- rolling team features
- lineup/availability snapshot
- market snapshot
- model version
- prediction
- final verified result

The raw source payload is retained separately so derived features can be reconstructed and audited.

## Market policy
Opening, intraday and closing quotes are stored independently. Decimal odds are converted to implied probabilities and normalized for overround before model-vs-market comparison. Missing or stale quotes are excluded rather than imputed with synthetic values.

## Training policy
Historical training uses chronological splits. No post-tip features may enter a pregame row. Models require out-of-sample evaluation before promotion. Calibration and closing-line behavior are tracked alongside raw prediction accuracy.

## Source policy
Sofascore observations are not automatically treated as ground truth. Final results should be independently verified before entering the verified training target table. Secondary market/result providers remain disabled until their schemas and reliability are validated.
