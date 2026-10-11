# Elite MatchMaster — Basketball TITAN Brain

## Purpose
A sport-specific basketball intelligence layer under UMIOS. It converts fixture, lineup, pace, efficiency, shot-profile, rest, market, and uncertainty inputs into calibrated probabilities and explicit abstention decisions.

## Core modules
1. Possession Engine — estimates possessions and possession variance.
2. Efficiency Engine — opponent-adjusted offensive and defensive efficiency.
3. Player Impact + Lineup Engine — expected minutes, availability, usage, creation, rim protection, rebounding, and continuity.
4. Shot Profile Engine — rim, mid-range, three-point volume/efficiency, and free throws.
5. Regime/Volatility Engine — pace, defense, foul, injury, and blowout regimes.
6. Rest/Fatigue Engine — rest, travel, back-to-back scheduling, and workload.
7. Market Intelligence — compares model probability with market-implied probability and line movement.
8. Possession Monte Carlo — produces distributions for moneyline, spread, total, team totals, halves, and quarters.
9. Adversarial Layer — stress-tests pace, shooting variance, fouls, injuries, and rotations.
10. Calibration + Abstention — tracks Brier/log loss and allows NO_BET when uncertainty dominates.

## Output contract
Each prediction should expose market, selection, probability, fair price, market price, edge, uncertainty, regime, key drivers, adversarial failure modes, data freshness, model version, and decision (BET/WATCH/NO_BET).

## Guardrails
External prediction sites are evidence, never ground truth. Stale lineups or odds must be flagged. Basketball parameters remain isolated from football. Predictive superiority must be established with out-of-sample evaluation before being claimed.
