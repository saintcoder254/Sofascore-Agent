from umios_probability import UMIOSProbabilityEngine


def test_monte_carlo_never_runs_below_one_million_trials():
    assert UMIOSProbabilityEngine.effective_simulation_count(1_000) == 1_000_000
    assert UMIOSProbabilityEngine.effective_simulation_count(10_000) == 1_000_000
    assert UMIOSProbabilityEngine.effective_simulation_count(1_000_000) == 1_000_000
    assert UMIOSProbabilityEngine.effective_simulation_count(2_000_000) == 2_000_000


def test_monte_carlo_invalid_request_uses_production_floor():
    assert UMIOSProbabilityEngine.effective_simulation_count(None) == 1_000_000
    assert UMIOSProbabilityEngine.effective_simulation_count("invalid") == 1_000_000
