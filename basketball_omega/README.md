# Basketball OMEGA Fusion Core

This package is the basketball-specific intelligence layer for Elite MatchMaster. It deliberately does not reuse football goal/Poisson assumptions.

## Agent graph

Availability/Minutes -> Player Impact -> Lineup Synergy -> Possession Efficiency -> Matchup Interaction -> Correlated Monte Carlo -> Market Residual -> Adversarial Challenge -> Final Arbiter.

Each agent emits an auditable opinion. The arbiter does not use a simple majority vote: disagreement, missing evidence, and adversarial challenges can force NO_BET.

## Learned upgrades implemented

- player impact with sample-size shrinkage and expected-minute weighting
- injury-to-minutes translation
- 5-man lineup evidence with small-sample shrinkage
- pace + ORtg/DRtg possession model
- matchup interaction layer
- correlated basketball Monte Carlo rather than football goal simulation
- market-relative residual analysis
- proper scoring-rule calibration agent
- adversarial disagreement and injury-risk gate
- auditable fusion contract for future model replacement

## Important

The stochastic simulator is a distribution engine, not a source of truth. It must be trained/backtested against historical NBA data before production betting decisions. No edge is considered guaranteed.
