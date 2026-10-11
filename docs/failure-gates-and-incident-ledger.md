# Failure gates and live incident ledger

## What changed
- Historical failure gate v2 validates the market, selection, probability, decimal odds and supplied edge against the probability/price-derived edge; missing justification and unexplained market disagreement block.
- Double-chance/DNB gate v2 separates probability edge (percentage points) from expected value, enforces probability/edge/EV floors, requires an adverse-branch test, regime sensitivity and market confirmation, and rejects a stress branch inconsistent with X2/1X.
- `failure_incident_ledger.py` appends each audited decision and subsequent settlement as JSON Lines. It never rewrites historical rows.
- `EMM_FAILURE_LEDGER_PATH` can point the ledger at a persistent writable path.

## Double-chance price arithmetic
For decimal odds (o) and model probability (p):
- implied probability = (1/o)
- probability edge = (p - 1/o)
- expected value per unit = (p 	imes o - 1)

The defaults require p >= 0.60, probability edge >= 0.03, and EV >= 0.03. These are separate checks. At p=0.715 and odds=1.44, the edge is about 2.06 percentage points and EV is 2.96%, so both strict 3% floors fail.

## Ledger format and operation
Each prediction audit stores fixture, market, selection, odds, raw probability, model version, both gate results, final state, blockers and warnings. Once the actual result is known, append a settlement event with `references_event_id`, `outcome` (1=win, 0=loss), final score and notes. Never backfill an outcome into the original prediction row; this preserves audit history and avoids hindsight contamination.

Example:
```python
from failure_incident_ledger import FailureIncidentLedger

ledger = FailureIncidentLedger()  # uses EMM_FAILURE_LEDGER_PATH or data/failure_incident_ledger.jsonl
row = ledger.record_decision(
    event=event, prediction=prediction, final_state="NO_BET",
    failure_gate=historical_gate_result, double_chance_gate=dc_gate_result,
    blockers=["DC_EDGE_BELOW_MINIMUM"], warnings=[]
)
ledger.record_settlement(row["event_id"], outcome=0, final_score="3-1",
                         notes="Settled from independently verified result")
```

## Production requirement
A local JSONL file is suitable for development and a persistent mounted disk. Serverless instances (including typical Vercel functions) may have ephemeral/read-only filesystems and multiple concurrent instances; for production, set the path to a persistent mounted volume or replace the storage backend with a transactional database/object store. This patch does not claim deployment or durable production storage has been verified.

## Regression case: Crystal Palace vs Nottingham Forest, 11 October 2026
The ticket selected X2 at 1.44 and settled as a loss (3-1). This is stored as a retrospective incident, not as proof that the native pipeline emitted the model probability. The prior 71.5% figure was an independent/manual estimate; the native prediction row, timestamped odds feed, stress evidence and calibration record were not verified. Therefore the ledger seed uses null model probability and explicitly labels the record retrospective.
