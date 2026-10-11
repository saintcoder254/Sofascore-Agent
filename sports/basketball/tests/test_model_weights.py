from sports.basketball.model_weights import ModelPerformance, weight_models

def test_model_weights_sum_to_one():
    weights = weight_models([
        ModelPerformance("a", .10, .20, 300, .02),
        ModelPerformance("b", .20, .30, 300, .05),
    ])
    assert abs(sum(weights.values()) - 1) < 1e-9
