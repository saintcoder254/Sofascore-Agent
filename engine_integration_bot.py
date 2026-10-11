"""Runtime integration audit for Elite MatchMaster match analysis.

This bot is deliberately non-blocking: it audits the real output of the existing
pipeline, records which engines were wired/observed, and flags integration gaps.
It never fabricates an engine result and never suppresses the best-available
forecast merely because an audit or live certification is incomplete.
"""
from __future__ import annotations

import importlib.util
import time
from typing import Any


class EngineIntegrationBot:
    VERSION = "EMM-ENGINE-INTEGRATION-BOT-1.0"

    # Module -> evidence that demonstrates the engine's result reached analysis.
    EXPECTED = {
        "umios_market_models": ("market_models", "market_models"),
        "basketball_probability_engine": ("basketball", "competition_regime"),
        "competition_regime_agent": ("regime", "competition_regime"),
        "empirical_goal_engine": ("empirical", "omega_empirical"),
        "dynamic_strength_engine": ("dynamic_strength", "dynamic_strength"),
        "competition_regime_engine": ("competition_regime", "competition_regime"),
    }

    def __init__(self, repository="saintcoder254/Sofascore-Agent"):
        self.repository = repository

    @staticmethod
    def _has_path(payload: Any, path: str) -> bool:
        current = payload
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        return current is not None

    def audit(self, probability_engine=None, prediction=None, analysis=None,
              qualification=None, arbiter=None) -> dict:
        prediction = prediction if isinstance(prediction, dict) else {}
        analysis = analysis if isinstance(analysis, dict) else {}
        qualification = qualification if isinstance(qualification, dict) else {}
        arbiter = arbiter if isinstance(arbiter, dict) else {}
        rows = []
        missing = []
        for module_name, (attribute, output_path) in self.EXPECTED.items():
            installed = importlib.util.find_spec(module_name) is not None
            wired = probability_engine is not None and getattr(probability_engine, attribute, None) is not None
            observed = self._has_path(prediction, output_path)
            if not installed:
                state = "MODULE_UNAVAILABLE"
            elif not wired:
                state = "INSTALLED_NOT_WIRED"
            elif observed:
                state = "OUTPUT_OBSERVED"
            else:
                state = "WIRED_OUTPUT_NOT_OBSERVED"
            if state != "OUTPUT_OBSERVED":
                missing.append({"engine": module_name, "state": state,
                                "expected_attribute": attribute,
                                "expected_output": output_path})
            rows.append({"engine": module_name, "module_available": installed,
                         "wired_to_probability_engine": wired,
                         "output_observed": observed, "state": state})

        prediction_exists = bool(prediction) and prediction.get("state") not in {
            "ERROR", "EXCEPTION"
        }
        # This is a diagnostic status, never a prediction veto.
        return {
            "bot": self.VERSION,
            "repository": self.repository,
            "generated_at": time.time(),
            "prediction_preserved": prediction_exists,
            "qualification_state": qualification.get("state", "NOT_PROVIDED"),
            "arbiter_state": arbiter.get("state", "NOT_PROVIDED"),
            "analysis_output_present": bool(analysis),
            "engine_count": len(rows),
            "observed_count": sum(row["state"] == "OUTPUT_OBSERVED" for row in rows),
            "gap_count": len(missing),
            "engines": rows,
            "integration_gaps": missing,
            "policy": {
                "non_blocking": True,
                "missing_engine_output_suppresses_forecast": False,
                "never_fabricate_engine_output": True,
                "missing_evidence_should_reduce_confidence": True,
                "audit_is_not_proof_of_model_accuracy": True,
            },
            "next_action": "REVIEW_INTEGRATION_GAPS" if missing else "NO_GAP_DETECTED_IN_REGISTERED_ENGINES",
        }
