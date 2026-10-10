"""Opt-in live smoke test for public football-data providers.

This is an acquisition diagnostic, not a prediction or qualification test.
It never places bets and never upgrades an event to qualified.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Executing a script by path puts scripts/ rather than the repository root on
# sys.path. Add the root explicitly so root-level adapters import reliably.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from feed_fusion import FeedFusionAdapter


async def main():
    adapter = FeedFusionAdapter(
        os.getenv("SOFASCORE_BASE", "https://www.sofascore.com/api/v1"),
        timeout=float(os.getenv("LIVE_HTTP_TIMEOUT_SECONDS", "15")),
    )
    started = time.time()
    try:
        payload = await adapter.today_events()
        events = payload.get("events") or []
        metrics = adapter.metrics
        source_summary = {
            "active_source": payload.get("source") or adapter.active_source,
            "event_count": len(events),
            "retrieved_at_age_seconds": round(max(0, time.time() - float(payload.get("retrieved_at", started))), 2),
            "provider_metrics": {
                key: value for key, value in metrics.items()
                if key.endswith(("_attempts", "_success", "_failures"))
            },
            "events_with_trust_envelopes": sum(bool(e.get("data_trust")) for e in events),
            "trusted_events": sum((e.get("data_trust") or {}).get("state") == "TRUSTED" for e in events),
            "quarantined_events": sum((e.get("data_trust") or {}).get("state") == "QUARANTINED" for e in events),
            "verification_sources": len(((payload.get("verification") or {}).get("final_results") or {}).get("sources") or []),
            "verification_events": sum(
                len(s.get("events") or [])
                for s in (((payload.get("verification") or {}).get("final_results") or {}).get("sources") or [])
            ),
            "verification_conflicts": len(payload.get("verification_conflicts") or []),
        }
        print(json.dumps(source_summary, indent=2, sort_keys=True))
        if not events:
            raise RuntimeError("LIVE_SMOKE_FAILED: active source returned no parseable fixtures")
        if not source_summary["active_source"]:
            raise RuntimeError("LIVE_SMOKE_FAILED: active source is not identified")
        # A successful HTTP response alone is insufficient: require at least one
        # fixture identity and keep trust/qualification decisions separate.
        identifiable = sum(
            bool((e.get("homeTeam") or {}).get("name") and (e.get("awayTeam") or {}).get("name"))
            for e in events
        )
        if identifiable == 0:
            raise RuntimeError("LIVE_SMOKE_FAILED: no fixtures have both team names")
        print(f"LIVE_SMOKE_PASS acquisition_only identifiable_fixtures={identifiable}")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(main())
