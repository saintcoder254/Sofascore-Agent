# UMIOS TITAN — 10-Point Hardening v2

1. Incident reconstruction: persist model version, probability, odds, history, simulation metadata and arbiter diagnostics for replay.
2. Data integrity: freshness, fixture identity, verification conflicts and match-state gates remain hard blockers.
3. Market-specific modeling: totals, BTTS, handicaps, team totals, corners and cards require market-specific evidence.
4. Distribution-first simulation: Monte Carlo validates the same model and is never counted as an independent source.
5. Tail-risk defense: total markets are checked against losing-tail probability, not just headline probability.
6. Price/value defense: very short prices require materially higher model probability; edge and EV are separate gates.
7. Source diversity: totals/team-total selections require at least two independent market evidence channels.
8. Sample-depth defense: total markets require deeper historical support; thin samples terminate in NO_BET.
9. Adversarial final arbiter: suspicious edges, model-market divergence, volatility and unsupported specialist markets can only block.
10. Regression protection: incident cases are encoded as tests; calibration and settlement remain closed-loop.

Core rule: incomplete or contradictory evidence produces NO_BET. The system never fills a ticket just to reach a target number of selections.
