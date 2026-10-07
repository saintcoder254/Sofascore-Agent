from calibration_pipeline import CalibrationPipeline


def _rows(n=835):
    return [
        {
            "predicted_at": i,
            "fixture_id": f"f{i}",
            "market": "TOTAL",
            "p": min(.99, max(.01, .55 + (i % 2) * .1)),
            "y": 1.0 if i % 3 else 0.0,
        }
        for i in range(n)
    ]


def test_calibration_uses_multiple_forward_windows():
    out=CalibrationPipeline(min_train=50,min_test=20).run(_rows())
    assert out["state"]=="EVALUATED"
    assert out["window_count"] >= 2
    assert all(w["test_start"] >= 50 for w in out["windows"])
    assert out["live_adjustment"] is False


def test_calibration_shadows_without_two_windows():
    out=CalibrationPipeline(min_train=175,min_test=250).run(_rows(600))
    assert out["state"]=="SHADOW"
    assert out["window_count"] < 2
    assert out["candidate_pass"] is False
