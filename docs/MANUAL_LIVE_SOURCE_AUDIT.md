# Manual live source audit

This workflow is intentionally opt-in because it makes live requests to third-party sports-data services.

## Run it
1. Open **Actions → Manual live source audit** in GitHub.
2. Select **Run workflow** on the `feat/manual-live-source-audit` branch.
3. Keep the default 15-second provider timeout unless diagnosing slow responses.
4. Open the run log and retain the JSON summary as the audit record.

## Interpretation
- A pass means the configured feed-fusion path returned parseable fixtures with team identities at the time of the run.
- Provider success/failure counters, independent verification counts, conflicts, and trust-envelope counts are diagnostic observations.
- This does **not** prove that every fixture is independently verified, that lineups/odds are available, that any event passes UMIOS qualification, or that the application is production-ready.
- Never infer a bet from this workflow. Fixture-level analysis must still pass the full evidence, freshness, identity, market, and final-arbiter gates. Missing or conflicting evidence remains `BLOCKED — NO BET`.
- The workflow does not print raw provider payloads or secrets.
