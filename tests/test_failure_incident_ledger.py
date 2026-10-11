import json
from failure_incident_ledger import FailureIncidentLedger


def test_append_and_settlement_are_append_only(tmp_path):
    path = tmp_path / "incidents.jsonl"
    ledger = FailureIncidentLedger(str(path))
    original = ledger.append({"record_type": "prediction_audit", "fixture_id": "test-1", "final_state": "NO_BET"})
    settlement = ledger.record_settlement(original["event_id"], outcome=0, final_score="3-1")
    rows = ledger.read()
    assert len(rows) == 2
    assert rows[0]["event_id"] == original["event_id"]
    assert rows[1]["references_event_id"] == original["event_id"]
    assert rows[1]["outcome"] == 0
    assert json.loads(path.read_text().splitlines()[0])["fixture_id"] == "test-1"


def test_invalid_outcome_rejected(tmp_path):
    ledger = FailureIncidentLedger(str(tmp_path / "incidents.jsonl"))
    try:
        ledger.record_settlement("missing", outcome=2)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid outcome must raise ValueError")
