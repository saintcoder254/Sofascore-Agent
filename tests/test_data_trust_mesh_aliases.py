"""Regression tests for provider-specific harmless team-name variants."""
import time

from data_trust_mesh import DataTrustMesh


def _event(home, away):
    return {
        "homeTeam": {"name": home, "score": None},
        "awayTeam": {"name": away, "score": None},
        "status": {},
    }


def test_trust_mesh_accepts_equivalent_team_labels_from_independent_sources():
    now = time.time()
    mesh = DataTrustMesh(max_age_seconds=180, min_independent_sources=2)
    result = mesh.evaluate([
        {"source": "espn", "retrieved_at": now, "payload": _event("FC Barcelona", "SK Rapid Wien")},
        {"source": "fotmob", "retrieved_at": now, "payload": _event("Barcelona", "Rapid Wien")},
    ], {"now": now})
    assert result["state"] == "TRUSTED"
    assert result["canonical"]["home"] == "FC Barcelona"
    assert result["canonical"]["away"] == "SK Rapid Wien"


def test_trust_mesh_still_rejects_reversed_fixture_orientation():
    now = time.time()
    mesh = DataTrustMesh(max_age_seconds=180, min_independent_sources=2)
    result = mesh.evaluate([
        {"source": "espn", "retrieved_at": now, "payload": _event("Barcelona", "Rapid Wien")},
        {"source": "fotmob", "retrieved_at": now, "payload": _event("Rapid Wien", "Barcelona")},
    ], {"now": now})
    assert result["state"] == "QUARANTINED"
