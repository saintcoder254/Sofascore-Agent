# Basketball / Football Independence Contract

Basketball OMEGA is a separate mathematical and runtime domain.

## Hard boundaries

- Basketball code lives under `basketball_omega/`.
- Basketball does not import `umios_*`, football market models, football Poisson logic, or the football Store.
- Basketball has its own contracts, router, point-in-time snapshot schema, SQLite ledger, orchestrator, learning state, calibration, CLV, and promotion path.
- The standalone service is `basketball_omega.service:app`.
- The existing football `app.py` remains unchanged by this boundary hardening.
- No merge into `main` is performed by this change.

## Point-in-time rule

A feature is eligible for a historical prediction only if its source timestamp is no later than the prediction timestamp. Injury, availability, lineup, odds, and player-state observations must therefore be snapshotted rather than read from today's final state.

## Promotion rule

Basketball changes remain on the basketball feature branch until dedicated tests, repository regression tests, and out-of-sample promotion gates pass.
