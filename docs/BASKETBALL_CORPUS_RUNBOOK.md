# Basketball OMEGA historical corpus runbook

1. Enumerate game keys by season from an approved source.
2. Fetch through HTTPJSONTransport with rate limiting and retries.
3. Archive raw payloads by SHA-256 before normalization.
4. Convert source payloads into SourceRecord.
5. Normalize and run the hard quality gate.
6. Reconcile duplicate/conflicting source observations without silently overwriting evidence.
7. Generate PIT snapshots for every prediction cutoff.
8. Extract PBP-derived features only from events available at the cutoff.
9. Build chronological training examples.
10. Run expanding-window OOS candidates.
11. Score Brier, log-loss, ECE, margin MAE, total MAE and CLV.
12. Require at least 250 genuine OOS games for promotion.

The repository intentionally does not commit a large third-party historical corpus. Acquisition is reproducible and checkpointed; raw evidence should be retained in the configured evidence store subject to source terms.
