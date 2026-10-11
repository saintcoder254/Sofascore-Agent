"""Repository loadability smoke tests.

These tests are deliberately offline: they verify imports, route registration,
and fail-closed qualification without depending on external sports-data providers.
"""
import importlib


def test_application_imports_and_registers_health_routes():
    app_module = importlib.import_module("app")
    paths = {getattr(route, "path", None) for route in app_module.app.routes}
    assert "/health" in paths
    assert "/status" in paths
    assert "/telemetry" in paths
    assert "/analyze/fixture/{event_id}" in paths


def test_qualifier_fails_closed_on_missing_evidence():
    from umios_qualifier import UMIOSQualifier

    result = UMIOSQualifier(stale_after=180).qualify(
        "fixture-test",
        {},
        now=1_800_000_000,
    )
    assert result["state"] == "NO_BET"
    assert result["blockers"]
    assert result["checks"]["freshness"] is False
    assert result["checks"]["fixture_identity"] is False


def test_market_model_does_not_emit_non_finite_probabilities():
    from umios_market_models import UMIOSMarketModels

    result = UMIOSMarketModels().evaluate(
        {"homeTeam": {"id": "h"}, "awayTeam": {"id": "a"}},
        {"history": {"home": {"events": []}, "away": {"events": []}}},
    )
    probabilities = result["probabilities"]
    for market in probabilities.values():
        for probability in market.values():
            assert isinstance(probability, (int, float))
            assert probability == probability  # not NaN
            assert 0.0 <= probability <= 1.0
