# UMIOS TITAN — 10-Point Hardening

1. Incident reconstruction: persisted predictions retain model version, probability, odds, history and simulation metadata for replay.
2. Data audit: freshness and verification remain hard gates; basketball has a dedicated model path.
3. Probability correction: basketball no longer uses the football Poisson-goals engine.
4. Market-specific modeling: total-points probabilities are evaluated at the exact bookmaker line.
5. Simulation correction: correlated team scoring with a shared pace/scoring shock; 5,000+ simulations.
6. Tail-risk defense: recent totals, H2H totals, model-line distance and simulated tail probability are checked.
7. Competition regime: youth/reserve/friendly competitions receive stricter sample requirements.
8. Confidence separation: raw probability, market edge and calibration are distinct signals.
9. NO_BET enforcement: insufficient evidence or unsupported model regimes terminate prediction.
10. Regression protection: automated tests cover basketball routing, thin-history rejection, guard applicability and incident diagnostics.

The objective is fewer, better-evidenced candidates rather than forced selections.
