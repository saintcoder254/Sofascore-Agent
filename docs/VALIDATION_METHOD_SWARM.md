# OMEGA Validation Method Swarm

## API
- `GET /validation/swarm/status` lists the diagnostic bots and their communication contract.
- `POST /validation/swarm/run` runs one fixture-level diagnostic pass.

Example request:
```json
{
  "fixture_id": "example-event-id",
  "expected_goals_home": 1.45,
  "expected_goals_away": 1.10,
  "market_odds_1x2": {"home": 2.10, "draw": 3.30, "away": 3.60},
  "historical_probability_samples": [0.51, 0.54, 0.49],
  "bayesian_evidence": [
    {"outcome": "home", "likelihood_ratio": 1.1, "source": "audited-evidence-id"}
  ],
  "monte_carlo_outcomes": [],
  "monte_carlo_batch_size": 100000
}
```
The short sample above is intentionally insufficient for the bootstrap bot; supply actual historical observations (at least 30) to obtain its interval. Convergence requires at least two full batches of ordered simulation outcomes. Never substitute generated or guessed values for evidence.

## Bots
- **Bootstrap Bot:** percentile-bootstrap 95% interval for the mean of supplied probability observations, 1,000 seeded resamples; requires at least 30 observations.
- **Sensitivity Bot:** analytical independent-Poisson forecast under ±20% individual and ±15% joint expected-goal perturbations.
- **Scenario Stress Bot:** adverse and high-/low-event scoring scenarios; scenarios are stress cases, not probability-weighted forecasts.
- **Bayesian Update Bot:** updates 1X2 priors with explicitly supplied likelihood ratios (0 < LR ≤ 100), records which evidence was applied, and warns that evidence is not independently authenticated.
- **Market Benchmark Bot:** removes 1X2 bookmaker overround and compares normalized market probabilities with the analytical model; publishes a message to the Bayesian bot's inbox. Market gaps are not silently converted into Bayesian likelihood ratios.
- **Convergence Bot:** compares the final ordered Monte Carlo batch against the preceding cumulative sample for home/draw/away frequencies; this is a stability diagnostic, not proof of correctness.

## Communication and safety
Every bot publishes a typed message to a shared per-run ledger. Messages include run ID, sender, recipient, topic, status, payload and timestamp. Targeted messages are routed to recipient inboxes; the final diagnostic arbiter consumes the bot statuses and publishes a summary. The API response includes the ledger so message exchange is inspectable.

The validation swarm is diagnostic only. It does not replace the fixture qualification gate, the native UMIOS probability engine, the mandatory one-million-trial Monte Carlo gate, calibration, walk-forward out-of-sample checks, historical-failure safeguards, or the production Final Arbiter. It never grants betting certification. Missing optional samples return `UNAVAILABLE`; invalid odds or malformed simulation outcomes return `BLOCK`. A successful API response or passing unit tests do not establish production deployment or live fixture execution.
