# OMEGA Data Trust Mesh

The Data Trust Mesh is the evidence firewall for Elite MatchMaster.

It is a deterministic agent mesh, not a collection of independent language
models. Agents communicate through a structured trust envelope so downstream
probability and market components receive both data and the evidence needed to
judge it.

Pipeline:

PROVENANCE -> FRESHNESS -> COMPLETENESS -> CONFLICT -> CONSENSUS -> ANOMALY -> SYNTHESIS -> QUARANTINE/TRUST

Rules:
1. Missing provenance is never silently accepted.
2. Stale evidence cannot become trusted because another field looks plausible.
3. Two observations from the same source are not independent witnesses.
4. Critical fixture/result conflicts quarantine the bundle.
5. A source may not overwrite a conflicting source without an explicit resolution rule.
6. Canonical results are emitted only from convergent evidence.
7. Scores, statuses, identities, and kickoff data are critical fields.
8. Odds may legitimately differ between bookmakers and are not hard-conflicted by this core mesh.
9. Missing values are never fabricated.
10. Every trust envelope is hash-addressed for auditability.

TRUSTED means evidence may enter downstream synthesis.
CAUTION means evidence exists but lacks sufficient independent confirmation.
QUARANTINED means downstream betting/prediction decisions must not use the bundle as validated truth.
