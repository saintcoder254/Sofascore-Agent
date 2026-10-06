# Basketball Player-State Intelligence v1

This stage adds four independent basketball components:

1. Player impact state: recursive Bayesian/Kalman-style updates with uncertainty.
2. Minutes distribution: expected minutes, confidence interval, and availability probability.
3. Replacement chain: identifies rotation candidates when a player is unavailable.
4. Lineup interaction: pairwise synergy with sparse-data shrinkage.

The implementation is deliberately transparent. It is a state-estimation foundation, not a claim that a Kalman filter alone is a validated NBA impact model.

Promotion still requires chronological out-of-sample validation. No football module is imported.
