# Basketball TITAN Historical Memory

Basketball TITAN now has a persistent, cutoff-aware historical retrieval layer.

The memory layer reads raw basketball observations from SQLite, bookmaker/market snapshots from the shared SQLite database, and verified pregame rows from the append-only historical dataset.

Every retrieval accepts a prediction cutoff timestamp. Observations captured after that cutoff are excluded. This prevents post-tip information from leaking into a pregame analysis.

The retrieval object is BasketballHistoricalMemory.build_context(...) and the API exposes POST /memory/context.

The returned context contains raw observations, market snapshots, verified historical rows, team history, source counts, and an explicit leakage-guard marker.

Recommended analysis flow:

acquire -> persist -> retrieve historical context -> build features -> simulate -> calibrate -> adversarial checks -> arbiter -> decision.

The memory layer is deliberately separated from the prediction engine so historical evidence can be reused by multiple basketball markets without duplicating storage.

Important: storage and retrieval are implemented in the branch, but a deployed production service must run this branch and point it at persistent storage for the accumulated database to survive restarts. A local SQLite file on an ephemeral container is not sufficient for durable production history.
