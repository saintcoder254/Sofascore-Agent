# Historical Failure Gate — OMEGA

## Purpose

This is a permanent anti-repeat layer for Elite MatchMaster OMEGA. It converts documented failure lessons into explicit questions that must be answered before a candidate selection reaches the Final Arbiter. It is a risk-control and calibration layer, not a prediction model.

## Mandatory questions

1. Favorite/short-price trap: Is a favorite or supposedly safe 1X/1/2 being selected while draw/upset risk remains unresolved?
2. Confidence inflation: Is confidence materially higher than independent evidence supports?
3. Probability vs value: Does the available price actually produce positive expected value?
4. Double counting: Are correlated signals being counted as independent evidence?
5. Recent-form overweight: Does the selection collapse when the latest matches are downweighted?
6. H2H overweight: Is a small, old, or low-relevance H2H sample driving the verdict?
7. Lineup uncertainty: Are injuries, suspensions, rotation, or final XI unknown?
8. Market disagreement: Does the bookmaker market disagree with the model, and if so, is there a documented reason?
9. Forced bet: Would NO BET be correct if the match were not already on the user's slip?
10. Empirical-model artifact: Does resampling/rounding create an implausible distribution that conflicts with independent models?
11. Monte Carlo overconfidence: Is simulation being treated as proof rather than a conditional stress test?
12. Calibration: Does historical performance justify the claimed probability/confidence band?

## Hard rule

A candidate is not approved because a majority of models like it. It must survive the failure gate, adversarial challenge, value gate, and Final Arbiter. A blocker means NO BET until the underlying evidence is resolved.

## Historical archetypes encoded

- Aston Villa-type failure: favorite/short-price double-chance selection with unresolved upset/draw risk.
- Liverpool-type failure: favorite confidence exceeds what the evidence and calibration justify.
- Mineros-type lesson: a plausible selection can still be a bad bet when the available price does not compensate for uncertainty.
- Empirical-engine lesson: an apparently sophisticated empirical simulation can become structurally misleading through venue sampling, averaging, and rounding; independent Poisson/DC checks remain mandatory.

## Execution order

Prediction -> Historical Failure Gate -> Adversarial Destruction -> Calibration -> Value -> Correlation Control -> Uncertainty Penalty -> Market Sanity -> Final Arbiter -> NO BET / APPROVE

## Anti-hallucination rule

The gate must report unavailable/unknown evidence rather than inventing answers. No historical incident, lineup, odds movement, Monte Carlo run, or calibration statistic may be asserted unless actually retrieved or computed.
