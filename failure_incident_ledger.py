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
        # DATABASE_URL selects durable PostgreSQL (e.g. Neon or Supabase).
        # Explicit path selects local JSONL for tests/development.
        self.database_url = None if path else os.getenv("DATABASE_URL")
        self.path = Path(path or os.getenv("EMM_FAILURE_LEDGER_PATH", "data/failure_incident_ledger.jsonl"))
        if self.database_url:
            self._ensure_database()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed") from exc
        return psycopg.connect(self.database_url, connect_timeout=5)

    def _require_storage(self) -> None:
        """Disallow ephemeral JSONL storage in serverless/production runtimes."""
        production = bool(os.getenv("VERCEL") or os.getenv("NODE_ENV", "").lower() == "production" or os.getenv("APP_ENV", "").lower() == "production")
        if production and not self.database_url:
            raise RuntimeError("DATABASE_URL is required for the production incident ledger; refusing ephemeral JSONL storage")

    def _ensure_database(self) -> None:
        # JSONB preserves the complete immutable event while event_id supports uniqueness.
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS emm_failure_incident_ledger (
                        sequence_id BIGSERIAL PRIMARY KEY,
                        event_id TEXT NOT NULL UNIQUE,
                        record_type TEXT NOT NULL,
                        market TEXT,
                        selection TEXT,
                        references_event_id TEXT,
                        payload JSONB NOT NULL,
                        recorded_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS emm_failure_market_selection_idx ON emm_failure_incident_ledger (market, selection)")
                cur.execute("CREATE INDEX IF NOT EXISTS emm_failure_reference_idx ON emm_failure_incident_ledger (references_event_id)")
            conn.commit()

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Append one immutable event; returns the exact persisted event."""
        self._require_storage()
        event = dict(record)
        event.setdefault("event_id", str(uuid.uuid4()))
        event.setdefault("ledger_version", self.VERSION)
        event.setdefault("recorded_at_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        event.setdefault("record_type", "prediction_audit")
        # Index market/selection at the event level for historical diagnostics.
        selection_details = event.get("selection")
        if isinstance(selection_details, dict):
            event.setdefault("market", selection_details.get("market"))
            event.setdefault("selection", selection_details.get("selection"))
        if self.database_url:
            # A failed durable write propagates to the arbiter, which must fail closed.
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO emm_failure_incident_ledger
                           (event_id, record_type, market, selection, references_event_id, payload)
                           VALUES (%s, %s, %s, %s, %s, %s::jsonb)""",
                        (event["event_id"], event["record_type"], event.get("market"),
                         event.get("selection"), event.get("references_event_id"),
                         json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)),
                    )
                conn.commit()
            return event
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

    def historical_summary(self, market: str, selection: str, min_samples: int = 20) -> Dict[str, Any]:
        """Summarize settled matching picks without treating unsettled forecasts as losses."""
        rows = self.read()
        settled_by_id = {
            row.get("references_event_id"): row
            for row in rows
            if row.get("record_type") == "settlement" and row.get("references_event_id")
        }
        outcomes = []
        for row in rows:
            same_market = str(row.get("market") or "").upper() == str(market or "").upper()
            same_selection = str(row.get("selection") or "").upper() == str(selection or "").upper()
            if not (same_market and same_selection):
                continue
            settlement = settled_by_id.get(row.get("event_id"))
            outcome = settlement.get("outcome") if settlement else row.get("outcome")
            if outcome not in (0, 1):
                continue
            probability = row.get("model_probability_raw")
            try:
                probability = float(probability) if probability is not None else None
            except (TypeError, ValueError):
                probability = None
            outcomes.append({"outcome": int(outcome), "probability": probability})
        calibrated = [row for row in outcomes if row["probability"] is not None and 0 <= row["probability"] <= 1]
        n = len(outcomes)
        calibrated_n = len(calibrated)
        return {
            "market": str(market or "").upper(),
            "selection": str(selection or "").upper(),
            "settled_samples": n,
            "wins": sum(row["outcome"] for row in outcomes),
            "losses": sum(1 - row["outcome"] for row in outcomes),
            "overall_observed_hit_rate": (sum(row["outcome"] for row in outcomes) / n) if n else None,
            # Compare predicted and observed probabilities on the same subset only.
            "observed_hit_rate": (sum(row["outcome"] for row in calibrated) / calibrated_n) if calibrated_n else None,
            "probability_samples": calibrated_n,
            "mean_predicted_probability": (sum(row["probability"] for row in calibrated) / calibrated_n) if calibrated_n else None,
            "min_samples_for_diagnostic": max(20, int(min_samples)),
            "diagnostic_ready": calibrated_n >= max(20, int(min_samples)),
        }

    def read(self) -> list[Dict[str, Any]]:
        self._require_storage()
        if self.database_url:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT payload FROM emm_failure_incident_ledger ORDER BY sequence_id")
                    return [row[0] for row in cur.fetchall()]
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
