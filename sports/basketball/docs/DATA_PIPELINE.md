# Basketball TITAN — Real Data Pipeline

## Acquisition boundary
Basketball data is isolated under `sports/basketball/`. The existing football acquisition stack is not modified to pretend it is basketball-aware.

## Data layers
1. Fixture layer — scheduled events, status, teams, competition, tipoff.
2. Result layer — final scores and overtime state.
3. Event layer — incidents and state transitions.
4. Lineup layer — starters, availability, expected minutes and substitutions where available.
5. Statistics layer — team/player box and advanced statistics where exposed.
6. Shot layer — shotmap and scoring profile where exposed.
7. Historical layer — prior team games and rolling windows.
8. Market layer — opening, current and closing lines.
9. Verification layer — independent confirmation before a result enters training truth.

## Feature rules
Pregame models may use only information timestamped before tipoff. Live models may use event data only after the event timestamp. Any feature whose timestamp cannot be established is quarantined.

## Training dataset contract
Every row should contain:
- fixture_id
- competition
- scheduled_tipoff
- snapshot_timestamp
- home/away identifiers
- team rolling features
- lineup/availability snapshot
- market snapshot
- model version
- prediction
- final verified result

The raw source payload is retained separately so derived features can be reconstructed and audited.
