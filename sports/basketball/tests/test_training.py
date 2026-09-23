from sports.basketball.training import TrainingRow, evaluate, chronological_split

def test_chronological_split_has_no_overlap():
    rows = [TrainingRow(100, 95, .6, 195, 195) for _ in range(10)]
    train, test = chronological_split(rows, .7)
    assert len(train) == 7
    assert len(test) == 3

def test_evaluation_is_deterministic():
    rows = [TrainingRow(100, 95, .8, 198, 195, 196, 195)]
    metrics = evaluate(rows)
    assert metrics.rows == 1
    assert metrics.brier_moneyline >= 0
    assert metrics.mae_total == 3
