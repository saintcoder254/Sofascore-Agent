"""Append-only JSONL ledger for prediction gate decisions and settled outcomes.

Use a persistent mounted volume or database in production. Serverless local disks may
be ephemeral; set EMM_FAILURE_LEDGER_PATH to a persistent writable location.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


class FailureIncidentLedger:
    VERSION = "EMM-FAILURE-INCIDENT-LEDGER-v1.0"
    _lock = threading.Lock()

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or os.getenv("EMM_FAILURE_LEDGER_PATH", "data/failure_incident_ledger.jsonl"))

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Append one immutable event; returns the exact persisted event."""
        event = dict(record)
        event.setdefault("event_id", str(uuid.uuid4()))
        event.setdefault("ledger_version", self.VERSION)
        event.setdefault("recorded_at_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        event.setdefault("record_type", "prediction_audit")
        line = json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return event

    def record_decision(self, *, event: Dict[str, Any], prediction: Dict[str, Any],
                        final_state: str, failure_gate: Dict[str, Any],
                        double_chance_gate: Dict[str, Any], blockers: list[str],
                        warnings: list[str]) -> Dict[str, Any]:
        selection = prediction.get("selection") or {}
        fixture = event.get("id") or event.get("event_id") or event.get("fixture_id")
        return self.append({
            "record_type": "prediction_audit",
            "fixture_id": fixture,
            "home_team": (event.get("homeTeam") or {}).get("name") or event.get("home_team"),
            "away_team": (event.get("awayTeam") or {}).get("name") or event.get("away_team"),
            "kickoff": event.get("startTimestamp") or event.get("kickoff"),
            "market": selection.get("market"),
            "selection": selection.get("selection"),
            "decimal_odds": selection.get("odds"),
            "model_probability_raw": selection.get("model_probability"),
            "model_probability_calibrated": selection.get("calibrated_probability"),
            "edge_supplied": selection.get("edge"),
            "expected_value_supplied": selection.get("expected_value"),
            "model_version": prediction.get("model_version"),
            "selection_justification": prediction.get("selection_justification"),
            "final_state": final_state,
            "failure_gate": failure_gate,
            "double_chance_gate": double_chance_gate,
            "blockers": list(blockers),
            "warnings": list(warnings),
            "settlement": None,
        })

    def record_settlement(self, event_id: str, *, outcome: int, settled_at: Optional[str] = None,
                          final_score: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        """Append a settlement event referencing the original event_id; do not rewrite history."""
        if outcome not in (0, 1):
            raise ValueError("outcome must be 1 for win or 0 for loss")
        return self.append({
            "record_type": "settlement",
            "references_event_id": event_id,
            "outcome": outcome,
            "settled_at": settled_at,
            "final_score": final_score,
            "notes": notes,
        })

    def read(self) -> list[Dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Corrupt JSONL at {self.path}:{line_number}") from exc
        return rows
