# OMEGA 2.0 Next Validation Phase

This phase defines point-in-time calibration, market benchmarking, and evidence-earned model weighting. Live probability changes remain disabled until settled out-of-sample validation meets minimum sample thresholds.


## Current implementation status

- Prediction persistence now uses PredictionLedgerGuard at decision time.
- Prediction records carry frozen_at, schema_version, and record_hash fields.
- Existing prediction databases are migrated in place when Store initializes.
- Store exposes ledger verification, calibration_ledger(), omega_weight_report(), and omega_calibration_report().
- Historical outcomes remain the only source for calibration; no automatic live reweighting is enabled.
- Integration tests were added for store freezing and calibration-ledger extraction.

## Validation requirement

The repository contains the test suite, but this environment has not executed the repository test suite successfully. Do not treat the new integration as production-validated until the project's runtime/CI executes the tests.


## Calibration/weight runtime wiring

The FastAPI service now exposes:
- GET /learning/omega for current ledger integrity, walk-forward calibration status, and evidence-earned model weights.
- POST /learning/omega/run for an explicit recalculation.

These endpoints are diagnostic/promotion-preparation only. The returned weights are not injected into live probability generation yet.

A model can therefore become EARNED in the report without silently changing production predictions. This separation is intentional.

## Promotion gate

Live reweighting remains disabled until:
1. the prediction ledger is point-in-time valid;
2. sufficient settled samples exist;
3. walk-forward calibration improves Brier score without worsening log loss;
4. model-level performance is demonstrated on the relevant market/competition slice;
5. closing-market benchmarking is available where applicable;
6. historical-failure gates remain non-bypassable.

No production model weight should be promoted merely because its in-sample score is better.
