from sports.basketball.analysis_memory import BasketballAnalysisMemoryGate


class StubMemory:
    def build_context(self, **kwargs):
        class Context:
            def as_dict(self):
                return {"cutoff_timestamp": kwargs["cutoff_timestamp"]}
        return Context()


def test_memory_gate_queries_before_analysis():
    gate = BasketballAnalysisMemoryGate(StubMemory())
    bundle = gate.query(
        cutoff_timestamp=1_700_000_000,
        fixture_id="fixture-1",
        home_team_id="1",
        away_team_id="2",
    )
    payload = bundle.as_dict()
    assert payload["memory_query"]["queried"] is True
    assert payload["memory_query"]["required_before_modeling"] is True


def test_memory_gate_rejects_invalid_cutoff():
    gate = BasketballAnalysisMemoryGate(StubMemory())
    try:
        gate.query(cutoff_timestamp=0)
    except ValueError as exc:
        assert "cutoff_timestamp" in str(exc)
    else:
        raise AssertionError("Expected invalid cutoff to be rejected")
