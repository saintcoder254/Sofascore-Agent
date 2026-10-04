# OMEGA 2.0 Upgrade

This upgrade adds the missing scientific-control layer identified by comparative research.

## New components
- Dynamic Strength Engine: recency-weighted, venue-aware, conservatively shrunk team strength.
- Calibration Engine: Brier, log loss, reliability bins, ECE.
- Model Health Engine: detects probability-quality/calibration degradation.
- Market Benchmark Engine: decision price, closing price, implied probabilities, CLV.
- Model Tournament: compares models on point-in-time settled predictions.
- Competition Regime Engine: league-specific scoring, draw, home-advantage, variance.
- Point-in-Time Ledger Guard: freezes prediction state and hashes the record.

## Design principle

Models do not receive permanent authority because they are sophisticated. Model weight must be earned through out-of-sample performance.

Market odds are a benchmark and adversary, not an oracle.

Missing evidence remains missing.

## Integration roadmap

1. Capture point-in-time prediction ledger.
2. Populate settled outcomes from independent verification.
3. Run calibration and model tournament.
4. Only then alter live ensemble weights.
5. Add dynamic strength to probability generation.
6. Add competition-regime priors.
7. Add closing-line/CLV evaluation.
8. Replace the current empirical resampling engine after distribution-level validation.

## Safety gates

No new component may manufacture odds, injuries, xG, lineups, or outcomes. Thin samples remain diagnostic-only. No retrospective information may enter a historical prediction record.
