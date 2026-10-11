from sports.basketball.store import BasketballStore

def test_store_roundtrip(tmp_path):
    store = BasketballStore(str(tmp_path / "basketball.db"))
    store.put_raw("test", "1", "abc", {"score": 100})
    store.put_features("1", {"pace": 99})
    counts = store.counts()
    assert counts == {"raw_observations": 1, "feature_snapshots": 1}
