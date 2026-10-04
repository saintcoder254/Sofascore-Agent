# OMEGA League Intelligence Engine

The League Intelligence Engine ranks competitions from settled point-in-time
prediction records already stored by OMEGA.

It is deliberately not a generic "best leagues in football" list. It measures
the leagues where the installed system has evidence of:

- sufficient settled sample depth;
- probability calibration;
- realized value at decision-time odds;
- closing-line value where closing odds exist;
- market coverage.

Scores are shrunk toward 50 for small samples. A league below the minimum
sample is marked INSUFFICIENT_SAMPLE; a league below the proven threshold is
PROVISIONAL. Neither status permits automatic live model reweighting.

The score is a research/prioritization metric, not a promise of future ROI.

## Required data

Each settled prediction should carry:

- features.competition (or features.league / features.tournament);
- decision-time odds;
- predicted probability;
- outcome;
- market;
- closing odds when available.

If the repository's historical database is absent or empty, the endpoint will
return an empty ranking rather than invent league performance.

## Score components

- Data depth: 20
- Calibration quality: 25
- Realized value: 25
- Closing-market benchmark: 15
- Market coverage: 15

Small samples are shrunk toward a neutral score of 50.

## Interpretation

PROVEN_CANDIDATE means the league has reached the configured settled-sample
threshold. It does not mean the league is guaranteed profitable.

PROVISIONAL means there is some evidence, but not enough to treat the ranking
as established.

INSUFFICIENT_SAMPLE means the league should not receive an automatic priority.

The ranking must be combined with today's fixture freshness, lineup
information, available prices, and the full OMEGA adversarial/value gates.
