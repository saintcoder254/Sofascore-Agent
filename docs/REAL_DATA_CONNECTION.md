# Basketball TITAN real-data connection

The basketball brain now has three explicit external-data boundaries:

1. SofaScore: primary fixture, event, statistics, incidents, lineups, and shotmap acquisition.
2. The Odds API: bookmaker moneyline, spread, and total acquisition. The provider requires an API key.
3. ESPN: independent postgame result verification for supported leagues.

The model core does not contain credentials and does not fabricate missing odds/results.

## Runtime activation

Set `THE_ODDS_API_KEY` in the deployment secret store. Do not place it in Git.
Set `BASKETBALL_ODDS_REGIONS` to the bookmaker region(s) you actually want.

The Odds API supports featured basketball markets including h2h, spreads, and totals, and provides historical odds on paid plans. Historical snapshots are suitable for leakage-safe opening/intraday/closing dataset construction.

The dataset builder only accepts snapshots captured before scheduled tipoff and only verified completed results.

## Current limitation

The repository now contains the live connection code, but a provider credential has not been supplied in this chat, so live bookmaker traffic cannot be authenticated yet. Once the secret is present in the deployment environment, the collector can begin accumulating real observations.
