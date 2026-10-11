"""Chronological walk-forward calibration evaluation; never applies live changes."""
import math
from calibration_engine import CalibrationEngine


class CalibrationPipeline:
    VERSION = "OMEGA-CALIBRATION-PIPELINE-v2"

    def __init__(self, min_train=50, min_test=20):
        self.min_train = max(20, int(min_train))
        self.min_test = max(10, int(min_test))
        self.engine = CalibrationEngine()

    @staticmethod
    def _usable(row):
        try:
            p = float(row["p"])
            y = float(row["y"])
            ts = float(row["predicted_at"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
        return (math.isfinite(p) and math.isfinite(y) and math.isfinite(ts)
                and 0.0 <= p <= 1.0 and 0.0 <= y <= 1.0)

    def run(self, ledger):
        supplied = list(ledger or [])
        rows = sorted(
            [r for r in supplied if self._usable(r)],
            key=lambda r: float(r["predicted_at"]),
        )
        invalid_rows = len(supplied) - len(rows)
        minimum = self.min_train + self.min_test
        if len(rows) < minimum:
            return {
                "version": self.VERSION, "state": "SHADOW", "samples": len(rows),
                "invalid_rows": invalid_rows, "minimum": minimum, "live_adjustment": False,
                "reason": "INSUFFICIENT_SETTLED_VALID_ROWS",
            }

        split = max(self.min_train, int(len(rows) * 0.70))
        train, test = rows[:split], rows[split:]
        if len(test) < self.min_test:
            return {
                "version": self.VERSION, "state": "SHADOW", "samples": len(rows),
                "invalid_rows": invalid_rows, "minimum": minimum,
                "train_samples": len(train), "test_samples": len(test),
                "live_adjustment": False, "reason": "INSUFFICIENT_CHRONOLOGICAL_TEST_ROWS",
            }

        mapping = {}
        edges = [i / 10 for i in range(11)]
        for lo, hi in zip(edges[:-1], edges[1:]):
            # Last bin includes probability exactly 1.0.
            selected = [r for r in train if lo <= float(r["p"]) < hi
                        or (hi == 1.0 and float(r["p"]) == 1.0)]
            if len(selected) >= 10:
                mapping[(lo, hi)] = sum(float(r["y"]) for r in selected) / len(selected)

        raw = self.engine.evaluate(test)
        calibrated = []
        for row in test:
            p = float(row["p"])
            q = p
            for (lo, hi), rate in mapping.items():
                if lo <= p < hi or (hi == 1.0 and p == 1.0):
                    q = 0.7 * p + 0.3 * rate
                    break
            calibrated.append({"p": q, "y": float(row["y"])})

        candidate = self.engine.evaluate(calibrated)
        passed = bool(
            mapping
            and candidate["brier"] is not None
            and raw["brier"] is not None
            and candidate["log_loss"] is not None
            and raw["log_loss"] is not None
            and candidate["brier"] < raw["brier"]
            and candidate["log_loss"] <= raw["log_loss"]
        )
        return {
            "version": self.VERSION, "state": "EVALUATED", "samples": len(rows),
            "invalid_rows": invalid_rows, "train_samples": len(train), "test_samples": len(test),
            "baseline": raw, "candidate": candidate, "mapping_bins": len(mapping),
            "candidate_pass": passed, "live_adjustment": False,
        }
