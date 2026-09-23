from sports.basketball.dataset import HistoricalDataset, PregameRow

def test_dataset_roundtrip(tmp_path):
    dataset = HistoricalDataset(str(tmp_path / "pregame.jsonl"))
    row = PregameRow("1", "NBA", 1.0, .5, "10", "20", {"pace": 99}, {"total": 220},
                     1, 225, True)
    dataset.append(row)
    assert len(dataset.read_verified()) == 1
