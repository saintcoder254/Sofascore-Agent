"""Fixture-level audit artifact for UMIOS/Omega analysis.

The artifact is evidence reporting, not a probability model. Missing evidence remains
explicitly unverified and cannot be promoted to a passing state.
"""
import hashlib
import json
import os
import time


def _as_float(value):
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _event_team(event, side):
    return (event.get(side + "Team") or {}).get("name")


def _market_rows(odds_bundle):
    rows = []
    if not isinstance(odds_bundle, dict):
        return rows
    for source_key, payload in odds_bundle.items():
        if not isinstance(payload, dict):
            continue
        for market in payload.get("markets") or []:
            if not isinstance(market, dict):
                continue
            for choice in market.get("choices") or []:
                if not isinstance(choice, dict):
                    continue
                raw_price = choice.get("decimalValue")
                if raw_price is None:
                    raw_price = choice.get("odds")
                price = _as_float(raw_price)
                if price is not None and price > 1:
                    rows.append({
                        "source_key": str(source_key),
                        "source": payload.get("source") or payload.get("provider") or source_key,
                        "market": market.get("name") or market.get("marketName"),
                        "selection": choice.get("name") or choice.get("label"),
                        "odds": price,
                        "retrieved_at": _as_float(payload.get("retrieved_at")),
                    })
    return rows


def build_fixture_audit(event_id, bundle, qualification, analysis, prediction, arbiter, generated_at=None):
    """Build a JSON-serializable, hash-addressed audit artifact from actual run outputs."""
    now = _as_float(generated_at) or time.time()
    bundle = bundle if isinstance(bundle, dict) else {}
    event = bundle.get("event") or {}
    trust = bundle.get("data_trust") or {}
    provenance = trust.get("provenance") or []
    if not provenance:
        verification = bundle.get("verification") or {}
        provenance = [
            {"source": source, "retrieved_at": _as_float(verification.get("retrieved_at"))}
            for source in (verification.get("sources") or [])
        ]
    sources = []
    for item in provenance:
        if not isinstance(item, dict):
            continue
        retrieved = _as_float(item.get("retrieved_at"))
        age = max(0.0, now - retrieved) if retrieved is not None else None
        sources.append({
            "source": item.get("source"),
            "retrieved_at": retrieved,
            "age_seconds": round(age, 3) if age is not None else None,
            "fresh": retrieved is not None and age <= 180,
            "payload_hash": item.get("payload_hash"),
        })
    trust_state = str(trust.get("state") or "NOT_VERIFIED").upper()
    trust_verified = trust_state == "TRUSTED" and not (trust.get("hard_blocks") or [])
    qual_state = str((qualification or {}).get("state") or "NOT_VERIFIED").upper()
    odds = _market_rows(bundle.get("odds"))
    odds_sources = sorted({str(row["source"]) for row in odds if row.get("source")})
    odds_timestamps = [row["retrieved_at"] for row in odds if row.get("retrieved_at") is not None]
    odds_verified = bool(odds and odds_sources and odds_timestamps and
                         all(max(0.0, now - stamp) <= 180 for stamp in odds_timestamps))
    selection = (prediction or {}).get("selection") or {}
    model_probability = _as_float(selection.get("model_probability"))
    model_name = (prediction or {}).get("model") or (analysis or {}).get("model")
    model_status = (
        "VALIDATED"
        if model_probability is not None and (prediction or {}).get("calibration_status") == "VALIDATED"
        else "EXTERNAL_OR_UNCALIBRATED" if model_probability is not None else "UNAVAILABLE"
    )
    ev = _as_float(selection.get("expected_value")) if selection else None
    decision_state = str((arbiter or {}).get("state") or "NO_BET").upper()
    if decision_state != "FINAL_QUALIFIED":
        final_verdict = "NO_BET"
    elif model_status != "VALIDATED" or not trust_verified or not odds_verified or ev is None or ev <= 0:
        final_verdict = "NO_BET"
    else:
        final_verdict = "BET_CANDIDATE_REQUIRES_EXTERNAL_REVIEW"

    artifact = {
        "schema": "ELITE_MATCHMASTER_FIXTURE_AUDIT_V1",
        "fixture_id": str(event_id),
        "generated_at": now,
        "repository": {
            "name": os.getenv("GITHUB_REPOSITORY", "saintcoder254/Sofascore-Agent"),
            "revision": os.getenv("GITHUB_SHA") or os.getenv("MATCHMASTER_REVISION") or "RUNTIME_REVISION_NOT_INJECTED",
        },
        "fixture": {
            "home": _event_team(event, "home"),
            "away": _event_team(event, "away"),
            "kickoff": event.get("startTimestamp") or event.get("timestamp") or event.get("date"),
            "status": ((event.get("status") or {}).get("type") or {}).get("state"),
            "identity_verified": bool(_event_team(event, "home") and _event_team(event, "away")),
        },
        "source_trust": {
            "state": trust_state,
            "verified": trust_verified,
            "hard_blocks": list(trust.get("hard_blocks") or []),
            "envelope_hash": trust.get("envelope_hash"),
            "sources": sources,
            "fresh_source_count": sum(source["fresh"] for source in sources),
            "independent_source_count": len({source["source"] for source in sources if source.get("source")}),
        },
        "qualification": {
            "state": qual_state,
            "integrity_score": (qualification or {}).get("integrity_score"),
            "checks": (qualification or {}).get("checks") or {},
            "blockers": list((qualification or {}).get("blockers") or []),
        },
        "market_odds": {
            "status": "VERIFIED_FRESH" if odds_verified else "NOT_VERIFIED",
            "source_count": len(odds_sources),
            "sources": odds_sources,
            "observation_count": len(odds),
            "retrieved_at_min": min(odds_timestamps) if odds_timestamps else None,
            "retrieved_at_max": max(odds_timestamps) if odds_timestamps else None,
            "observations": odds,
        },
        "probability_model": {
            "status": model_status,
            "model": model_name,
            "selection": selection.get("selection"),
            "market": selection.get("market"),
            "model_probability": model_probability,
            "expected_value": ev,
            "reason": None if model_status == "VALIDATED" else
                "No explicit validated calibration status was present in the runtime prediction output.",
        },
        "analysis": {
            "state": (analysis or {}).get("state") or "NOT_VERIFIED",
            "prediction_state": (prediction or {}).get("state") or "NOT_VERIFIED",
            "arbiter_state": decision_state,
            "arbiter_reason": (arbiter or {}).get("reason"),
            "final_verdict": final_verdict,
        },
    }
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"), default=str)
    artifact["artifact_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return artifact
