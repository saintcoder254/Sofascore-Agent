# OMEGA Case Database Mesh

Every football fixture analysed by Elite MatchMaster receives its own isolated SQLite case database plus a central registry.

The global Store remains the aggregate learning/calibration ledger. The case database is the forensic case file for one fixture.

## Case contents

case_meta: case identity and lifecycle.
observations: raw/verified evidence with source, stage, agent, payload hash, and parent hash.
trust_events: Data Trust Mesh envelopes.
model_runs: model inputs/outputs, simulation count, and hashes.
market_snapshots: odds and market evidence.
predictions: candidate/final prediction records.
arbiter_decisions: Final Arbiter result, blockers, and warnings.
failures: explicit integrity/failure-gate events.
audit_chain: append-only tamper-evident sequence linking all case events.

## Flow

SOURCE -> OBSERVATION -> TRUST -> MARKET/MODEL -> PREDICTION -> ARBITER -> FAILURE/VERDICT

## Integrity rules

1. No fabricated records are inserted.
2. Existing case prediction IDs are not silently overwritten.
3. Every persisted case event creates a chain entry.
4. Every chain entry has a payload hash and parent chain hash.
5. verify_chain() must pass for an internally consistent case.
6. Quarantined trust evidence and arbiter blockers remain recorded.

## API

GET /cases
GET /case/{fixture_id}
GET /case/{fixture_id}/audit
GET /case/{fixture_id}/trust
