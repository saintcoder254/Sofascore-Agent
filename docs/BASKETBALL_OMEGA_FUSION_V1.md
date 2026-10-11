# Basketball OMEGA Fusion v1

## Design decision
The basketball stack is separated from football logic because basketball scoring is possession-driven and player availability changes the distribution of minutes, usage, efficiency, and lineup combinations.

## Evidence hierarchy
1. Timestamp integrity and source agreement
2. Player availability and projected minutes
3. Player impact / lineup strength
4. Possession pace and efficiency
5. Matchup interactions
6. Score distribution simulation
7. Market residual and price
8. Calibration / out-of-sample performance
9. Adversarial challenge
10. Final decision

## NO_BET controls
NO_BET is preferred when independent models materially disagree, player availability is unresolved, historical samples are thin, or no market price exists for an actionable comparison.

## Future v2 targets
- Bayesian/Kalman player state updates
- RAPM/EPM-style player priors
- explicit substitution/minutes distribution
- hierarchical team/league effects
- learned residual market model
- opening/current/closing line and CLV ledger
- regime-specific calibration
- walk-forward model tournament
- possession-level foul/FT/3PA/turnover/rebound simulation
- injury contingency branching
