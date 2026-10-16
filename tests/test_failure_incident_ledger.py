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


def test_historical_summary_joins_settlements_and_excludes_unsettled(tmp_path):
    ledger = FailureIncidentLedger(str(tmp_path / "incidents.jsonl"))
    first = ledger.record_decision(
        event={"id": 42, "homeTeam": {"name": "Home"}, "awayTeam": {"name": "Away"}},
        prediction={"selection": {"market": "DOUBLE_CHANCE", "selection": "X2",
                                  "odds": 1.6, "model_probability": 0.70}},
        final_state="FINAL_QUALIFIED", failure_gate={}, double_chance_gate={},
        blockers=[], warnings=[],
    )
    ledger.record_decision(
        event={"id": 43, "homeTeam": {"name": "Home"}, "awayTeam": {"name": "Away"}},
        prediction={"selection": {"market": "DOUBLE_CHANCE", "selection": "X2",
                                  "odds": 1.6, "model_probability": 0.70}},
        final_state="FINAL_QUALIFIED", failure_gate={}, double_chance_gate={},
        blockers=[], warnings=[],
    )
    ledger.record_settlement(first["event_id"], outcome=1)
    summary = ledger.historical_summary("DOUBLE_CHANCE", "X2")
    assert summary["settled_samples"] == 1
    assert summary["wins"] == 1
    assert summary["probability_samples"] == 1
    assert summary["diagnostic_ready"] is False


def test_production_refuses_ephemeral_jsonl_without_database_url(tmp_path, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    ledger = FailureIncidentLedger(str(tmp_path / "incidents.jsonl"))
    try:
        ledger.append({"record_type": "prediction_audit", "fixture_id": "prod-no-db"})
    except RuntimeError as exc:
        assert "DATABASE_URL is required" in str(exc)
    else:
        raise AssertionError("production must not write the incident ledger to ephemeral JSONL")

