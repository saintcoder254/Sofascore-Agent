"""SofaScore HTTP 403 diagnostic swarm.

Runs independent, bounded diagnostic workers concurrently:
- SofaScore scheduled-events endpoint probe through the existing adapter
- public ESPN fallback acquisition
- public FotMob fallback acquisition
- local adapter/configuration inspection

This is diagnostic only. It does not evade access controls, rotate identities,
solve challenges, or treat a 403 as a transient error to hammer. A 403 is
reported as an access-policy/provider response; the pipeline should fail over
to independently validated feeds and preserve trust gates.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import platform
import time
from typing import Any

import httpx

from sofascore_adapter import SofaScoreAdapter
from fotmob_adapter import FotMobAdapter
from feed_fusion import FeedFusionAdapter


def _safe_error(exc: BaseException) -> str:
    # Avoid dumping request headers, cookies, tokens, or full response bodies.
    return f"{type(exc).__name__}: {str(exc)[:240]}"


async def _sofascore_worker(timeout: float) -> dict[str, Any]:
    base = os.getenv("SOFASCORE_BASE", "https://www.sofascore.com/api/v1")
    adapter = SofaScoreAdapter(base, timeout=timeout)
    started = time.perf_counter()
    try:
        payload = await adapter.today_events()
        events = payload.get("events") or []
        return {
            "worker": "sofascore_endpoint",
            "status": "PASS" if events else "EMPTY",
            "http_status": adapter.metrics.get("last_status_code"),
            "latency_ms": adapter.metrics.get("last_latency_ms"),
            "event_count": len(events),
            "identified_events": sum(bool((e.get("homeTeam") or {}).get("name")
                                          and (e.get("awayTeam") or {}).get("name"))
                                     for e in events),
        }
    except Exception as exc:
        status = adapter.metrics.get("last_status_code")
        classification = (
            "ACCESS_DENIED_403"
            if status == 403 else
            "RATE_LIMIT_429"
            if status == 429 else
            "UPSTREAM_SERVER_ERROR"
            if status and status >= 500 else
            "TRANSPORT_OR_PARSE_FAILURE"
        )
        return {
            "worker": "sofascore_endpoint",
            "status": "BLOCKED",
            "classification": classification,
            "http_status": status,
            "latency_ms": adapter.metrics.get("last_latency_ms"),
            "error": _safe_error(exc),
            "action": (
                "Do not retry aggressively or bypass access controls. "
                "Use validated alternate providers; retry only after a cooldown "
                "or when provider access/configuration changes."
                if status == 403 else
                "Check provider status, timeout, and response parsing; preserve fail-closed gates."
            ),
        }
    finally:
        await adapter.close()


async def _espn_worker(timeout: float) -> dict[str, Any]:
    url = FeedFusionAdapter.ESPN_BASE
    day = dt.datetime.now(dt.timezone.utc).date().strftime("%Y%m%d")
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout, headers={
            "Accept": "application/json",
            "User-Agent": "EliteMatchMaster-public-feed-diagnostic/1.0",
        }) as client:
            response = await client.get(url, params={"dates": day})
            response.raise_for_status()
            payload = response.json()
        normalized = FeedFusionAdapter._normalize_espn(payload)
        events = normalized.get("events") or []
        return {
            "worker": "espn_fallback",
            "status": "PASS" if events else "EMPTY",
            "http_status": 200,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "event_count": len(events),
            "identified_events": sum(bool((e.get("homeTeam") or {}).get("name")
                                          and (e.get("awayTeam") or {}).get("name"))
                                     for e in events),
        }
    except httpx.HTTPStatusError as exc:
        return {"worker": "espn_fallback", "status": "FAIL",
                "http_status": exc.response.status_code, "error": _safe_error(exc)}
    except Exception as exc:
        return {"worker": "espn_fallback", "status": "FAIL", "error": _safe_error(exc)}


async def _fotmob_worker(timeout: float) -> dict[str, Any]:
    adapter = FotMobAdapter(timeout=timeout)
    try:
        payload = await adapter.today_events()
        events = payload.get("events") or []
        return {
            "worker": "fotmob_fallback",
            "status": "PASS" if events else "EMPTY",
            "http_status": adapter.metrics.get("last_status_code"),
            "event_count": len(events),
            "identified_events": sum(bool((e.get("homeTeam") or {}).get("name")
                                          and (e.get("awayTeam") or {}).get("name"))
                                     for e in events),
        }
    except Exception as exc:
        return {
            "worker": "fotmob_fallback",
            "status": "FAIL",
            "http_status": getattr(getattr(exc, "response", None), "status_code", None),
            "error": _safe_error(exc),
        }
    finally:
        await adapter.close()


def _configuration_worker() -> dict[str, Any]:
    return {
        "worker": "local_configuration",
        "status": "PASS",
        "python": platform.python_version(),
        "sofascore_base_configured": bool(os.getenv("SOFASCORE_BASE")),
        "timeout_seconds": float(os.getenv("SOFASCORE_SWARM_TIMEOUT_SECONDS", "12")),
        "policy": "no proxy rotation, challenge bypass, or aggressive retries",
    }


async def main() -> int:
    timeout = max(3.0, min(float(os.getenv("SOFASCORE_SWARM_TIMEOUT_SECONDS", "12")), 25.0))
    started = time.time()
    # Independent workers run concurrently to separate primary-provider failure
    # from general network failure and to test viable public fallbacks.
    results = await asyncio.gather(
        _sofascore_worker(timeout),
        _espn_worker(timeout),
        _fotmob_worker(timeout),
        return_exceptions=True,
    )
    normalized = []
    for index, result in enumerate(results):
        if isinstance(result, BaseException):
            normalized.append({"worker": f"worker_{index}", "status": "ERROR",
                               "error": _safe_error(result)})
        else:
            normalized.append(result)
    normalized.append(_configuration_worker())

    sofascore = next((r for r in normalized if r.get("worker") == "sofascore_endpoint"), {})
    fallback_passes = [
        r for r in normalized
        if r.get("worker") in {"espn_fallback", "fotmob_fallback"}
        and r.get("status") == "PASS"
        and r.get("identified_events", 0) > 0
    ]
    if sofascore.get("classification") == "ACCESS_DENIED_403":
        disposition = "SOFASCORE_BLOCKED_USE_VALIDATED_FALLBACK"
    elif sofascore.get("status") == "PASS":
        disposition = "SOFASCORE_RECOVERED"
    else:
        disposition = "SOFASCORE_NOT_CONFIRMED"
    report = {
        "schema_version": 1,
        "started_at_epoch": round(started, 3),
        "duration_seconds": round(time.time() - started, 2),
        "disposition": disposition,
        "fallbacks_with_identified_fixtures": [r["worker"] for r in fallback_passes],
        "workers": normalized,
        "safety_gate": (
            "Acquisition diagnostics do not establish independent verification, "
            "lineups, statistics, incidents, odds, or UMIOS qualification. "
            "Missing evidence remains BLOCKED — NO BET."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    # Return nonzero only if neither SofaScore nor a fallback returns identified
    # fixtures. A SofaScore 403 with working fallback is a handled degradation.
    if sofascore.get("status") != "PASS" and not fallback_passes:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
