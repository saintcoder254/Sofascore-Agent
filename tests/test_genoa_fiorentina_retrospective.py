"""Regression fixture from the 2026-10-10 Genoa vs Fiorentina screenshot.

This test deliberately validates only the visible pre-match probabilities and
illustrative market arithmetic. It does not pretend to recreate missing
pre-match evidence or certify the original betting decision.
"""
import unittest

class TestGenoaFiorentinaRetrospective(unittest.TestCase):
    def test_screenshot_probabilities_are_normalized(self):
        probabilities = {"home": 0.26, "draw": 0.36, "away": 0.38}
        self.assertAlmostEqual(sum(probabilities.values()), 1.0, places=8)
        self.assertEqual(max(probabilities, key=probabilities.get), "away")

    def test_reported_score_matches_away_win(self):
        home_score, away_score = 2, 3
        actual = "home" if home_score > away_score else "draw" if home_score == away_score else "away"
        self.assertEqual(actual, "away")

    def test_illustrative_away_odds_do_not_show_positive_ev_at_38_percent(self):
        # 2.36 was an illustrative price discussed in the retrospective,
        # not a verified historical closing price.
        model_probability = 0.38
        illustrative_decimal_odds = 2.36
        expected_return = model_probability * illustrative_decimal_odds - 1.0
        self.assertAlmostEqual(expected_return, -0.1032, places=6)
        self.assertLess(expected_return, 0.0)

    def test_single_match_result_does_not_certify_model_calibration(self):
        # One settled fixture cannot establish a calibration sample.
        settled_fixture_count = 1
        minimum_calibration_sample = 20
        self.assertLess(settled_fixture_count, minimum_calibration_sample)

if __name__ == "__main__":
    unittest.main()
