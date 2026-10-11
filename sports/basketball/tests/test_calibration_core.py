from sports.basketball.calibration_core import calibration_report

def test_calibration_report():
    report = calibration_report([.5, .5, .9, .9], [0, 1, 1, 1])
    assert report.sample_count == 4
    assert report.mean_absolute_gap >= 0
