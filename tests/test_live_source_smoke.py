"""Offline regression tests for the live-source smoke gate.

These tests exercise the live audit decision logic with a mocked fusion adapter;
they never make network requests and never turn acquisition into qualification.
"""
import asyncio
import contextlib
import io
import json

import scripts.live_source_smoke as smoke


class FakeAdapter:
    def __init__(self, payload):
        self.payload = payload
        self.active_source = payload.get("source")
        self.metrics = {"primary_attempts": 1, "primary_failures": 1, "espn_success": 1}

    async def today_events(self):
        return self.payload

    async def close(self):
        return None


def _payload(trust_state):
    return {
        "source": "espn",
        "retrieved_at": 1000.0,
        "events": [{
            "homeTeam": {"name": "Home FC"},
            "awayTeam": {"name": "Away FC"},
            "data_trust": {"state": trust_state},
        }],
        "verification": {"final_results": {"sources": [{"events": [{}]}]}},
        "verification_conflicts": [],
    }


def test_live_smoke_accepts_identifiable_fixture_with_trust(monkeypatch):
    monkeypatch.setattr(smoke, "FeedFusionAdapter", lambda *args, **kwargs: FakeAdapter(_payload("TRUSTED")))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        asyncio.run(smoke.main())
    report = json.loads(output.getvalue().split("LIVE_SMOKE_PASS")[0])
    assert report["active_source"] == "espn"
    assert report["event_count"] == 1
    assert report["trusted_events"] == 1
    assert "LIVE_SMOKE_PASS acquisition_and_trust identifiable_fixtures=1 trusted_fixtures=1" in output.getvalue()


def test_live_smoke_fails_closed_when_no_fixture_is_trusted(monkeypatch):
    monkeypatch.setattr(smoke, "FeedFusionAdapter", lambda *args, **kwargs: FakeAdapter(_payload("QUARANTINED")))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            asyncio.run(smoke.main())
        except RuntimeError as exc:
            assert "none passed the independent-source trust mesh" in str(exc)
        else:
            raise AssertionError("smoke audit must fail when no fixture passes the trust mesh")
    assert '"trusted_events": 0' in output.getvalue()
