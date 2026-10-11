from sports.basketball.analysis_memory import BasketballAnalysisMemoryGate
from sports.basketball.analysis_service import BasketballAnalysisService


class StubMemory:
    def build_context(self, **kwargs):
        class Context:
            def as_dict(self):
                return {
                    "cutoff_timestamp": kwargs["cutoff_timestamp"],
                    "raw_observations": [
                        {
                            "fixture_id": "old-1",
                            "observed_at": kwargs["cutoff_timestamp"] - 100,
                            "source": "test",
                            "payload": {
                                "status": {"type": "finished"},
                                "homeTeam": {"id": "1"},
                                "awayTeam": {"id": "2"},
                                "homeScore": {"current": 110},
                                "awayScore": {"current": 100},
                            },
                        }
                    ],
                    "market_snapshots": [],
                    "verified_rows": [],
                }
        return Context()


def test_analysis_consumes_memory_and_runs_simulation():
    service = BasketballAnalysisService(BasketballAnalysisMemoryGate(StubMemory()))
    result = service.analyze(
        cutoff_timestamp=1_700_000_000,
        home_team_id="1",
        away_team_id="2",
        simulations=100,
    )
    assert result.memory["cutoff_timestamp"] == 1_700_000_000
    assert result.projection["total_points"] > 0
    assert result.simulation["simulations"] == 100
