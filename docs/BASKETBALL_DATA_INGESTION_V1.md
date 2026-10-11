# Basketball OMEGA — Historical Data Ingestion Mesh v1

## Source strategy

The engine supports a primary/independent-source mesh rather than trusting one feed:
- **NBA Stats / nba_api** for official game, player, team, box-score, PBP, shot and lineup acquisition.
- **shufinskiy/nba_data** for long historical PBP, shot and matchup archives.
- **Basketball-Reference** for independent game/PBP cross-checks.

NBA PBP v3 exposes player IDs, action numbers, periods, clocks and descriptions. The historical nba_data archive spans PBP/shot data from 1996/97 and matchup data from 2017/18 onward.

## Bot pipeline

1. Source adapters acquire raw payloads.
2. Raw evidence is content-addressed and immutable-by-key.
3. Normalizer maps records to canonical basketball entities.
4. Quality agent detects identity, timestamp, score, minutes and duplicate anomalies.
5. Reconciliation agent compares independent sources and flags conflicts.
6. PIT agent requires BOTH effective time and capture time to be <= prediction cutoff.
7. Only the reconciled PIT snapshot can feed historical training.

## Hard safety rules

- Never use a post-cutoff observation in a historical feature.
- Never silently overwrite raw evidence.
- Never resolve source conflicts without recording the conflict.
- Never treat a single source as consensus.
- Never train on quarantined records.
- Never permit a snapshot with future effective/capture timestamps.
- Every normalized record retains source provenance.

This stage is the ingestion foundation. It does not claim that a historical corpus has already been downloaded into the repository.
