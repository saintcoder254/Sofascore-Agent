# Elite MatchMaster GitHub Agent Swarm

A bounded concurrent audit swarm for Sofascore-Agent. It does not claim that millions of autonomous bots are running.

## Agents
- Repository integrity: required files and prohibited hosting references.
- Test coverage: regression-test presence for core gates and ledger.
- Fail-closed audit: static NO_BET and gate handling checks.
- Durable storage: database adapter, dependency, and documentation checks; cannot inspect Vercel secrets or prove live I/O.
- Secret hygiene: heuristic scan for hard-coded credentials.
- Workflow security: least-privilege and bounded-run checks.
- Final arbiter: any BLOCK blocks certification; WARN requires human review.

## Communication
Agents execute concurrently and write structured findings into one shared report. GitHub Actions publishes JSON and Markdown artifacts. Each run has a single combined report rather than one message per agent.

## Triggers
- Manual: Actions → Elite MatchMaster Agent Swarm → Run workflow.
- Scheduled: every six hours.
- Automatic: relevant pull request changes and changes on main.

## Limits
This is a deterministic repository-audit swarm, not millions of autonomous AI models. It does not place bets, produce picks, provision a database, or access Vercel secrets. Production database verification still requires an authorized DATABASE_URL and a live append/read/settlement smoke test.
