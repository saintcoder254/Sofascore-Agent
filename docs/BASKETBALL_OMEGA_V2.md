# Basketball OMEGA v2 — Empirical Core

This release closes the principal architectural gaps identified in the Basketball
OMEGA audit.

Implemented layers:
- PIT-safe historical acquisition and manifesting
- Ridge-style RAPM-compatible player impact interface
- empirical minutes forecasting with availability distributions
- model-error independence weighting
- basketball score-distribution simulation
- independent moneyline/spread/total/1H/Q1/team-total/player-prop interfaces
- calibration suite with Brier, log-loss, ECE, and reliability buckets
- Basketball Digital Twin state contract
- chronological tournament runner and promotion gate

Important boundary: these are model engines and stable interfaces, not evidence that
the resulting model is empirically superior. Empirical promotion remains blocked
until a real historical corpus is acquired and a >=250-game OOS tournament passes.
