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
