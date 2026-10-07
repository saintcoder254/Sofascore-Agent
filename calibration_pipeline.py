"""OMEGA expanding-window calibration pipeline.

Calibration mappings are learned only from observations preceding each test
window. The pipeline never fits a calibration transform on future outcomes.
"""
from calibration_engine import CalibrationEngine


class CalibrationPipeline:
    VERSION = "OMEGA-CALIBRATION-PIPELINE-v3-EXPANDING-WALKFORWARD"

    def __init__(self, min_train=175, min_test=250, min_windows=2):
        self.min_train = max(175, int(min_train))
        self.min_test = max(250, int(min_test))
        self.min_windows = max(2, int(min_windows))
        self.engine = CalibrationEngine()

    @staticmethod
    def _mapping(train):
        mapping = {}
        for lo, hi in zip([.50, .60, .70, .80, .90], [.60, .70, .80, .90, 1.01]):
            rs = [r for r in train if lo <= float(r["p"]) < hi]
            if len(rs) >= 10:
                mapping[(lo, hi)] = sum(float(r["y"]) for r in rs) / len(rs)
        return mapping

    @staticmethod
    def _apply(rows, mapping):
        out = []
        for r in rows:
            p = float(r["p"])
            q = p
            for (lo, hi), rate in mapping.items():
                if lo <= p < hi:
                    q = .7 * p + .3 * rate
                    break
            out.append({"p": q, "y": r["y"]})
        return out

    def _windows(self, rows):
        ordered = sorted(
            [r for r in rows if r.get("predicted_at") is not None and r.get("p") is not None and r.get("y") is not None],
            key=lambda r: float(r["predicted_at"]),
        )
        windows = []
        train_end = self.min_train
        while train_end + self.min_test <= len(ordered):
            test_end = train_end + self.min_test
            train, test = ordered[:train_end], ordered[train_end:test_end]
            mapping = self._mapping(train)
            raw = self.engine.evaluate(test)
            calibrated = self.engine.evaluate(self._apply(test, mapping))
            windows.append({
                "window": len(windows) + 1,
                "train_samples": len(train),
                "test_samples": len(test),
                "test_start": float(test[0]["predicted_at"]),
                "test_end": float(test[-1]["predicted_at"]),
                "mapping_bins": len(mapping),
                "baseline": raw,
                "candidate": calibrated,
                "candidate_pass": bool(
                    raw.get("brier") is not None
                    and calibrated.get("brier") is not None
                    and calibrated.get("log_loss") is not None
                    and calibrated["brier"] <= raw["brier"]
                    and calibrated["log_loss"] <= raw["log_loss"]
                ),
            })
            train_end = test_end
        return windows

    def run(self, ledger):
        rows = sorted(
            [r for r in ledger if r.get("predicted_at") is not None and r.get("p") is not None and r.get("y") is not None],
            key=lambda r: float(r["predicted_at"]),
        )
        windows = self._windows(rows)
        if len(windows) < self.min_windows:
            return {
                "version": self.VERSION,
                "state": "SHADOW",
                "samples": len(rows),
                "minimum": self.min_train + self.min_test,
                "window_count": len(windows),
                "candidate_pass": False,
                "live_adjustment": False,
            }

        raw_rows, calibrated_rows = [], []
        for window in windows:
            # Metrics in each window are already computed from a strictly forward test.
            if not window["candidate_pass"]:
                raw_rows = []
                calibrated_rows = []
                break

        # Recompute aggregate metrics from the concatenated out-of-sample predictions
        # represented by the windows. This keeps the reported score tied to the same
        # chronological observations used for the gate.
        ordered = rows
        for window in windows:
            train_end = window["train_samples"]
            test_end = train_end + window["test_samples"]
            train = ordered[:train_end]
            test = ordered[train_end:test_end]
            mapping = self._mapping(train)
            raw_rows.extend(test)
            calibrated_rows.extend(self._apply(test, mapping))

        baseline = self.engine.evaluate(raw_rows) if raw_rows else None
        candidate = self.engine.evaluate(calibrated_rows) if calibrated_rows else None
        passed = bool(
            len(windows) >= self.min_windows
            and all(w["candidate_pass"] for w in windows)
            and baseline
            and candidate
            and candidate.get("brier") is not None
            and baseline.get("brier") is not None
            and candidate["brier"] <= baseline["brier"]
            and candidate.get("log_loss") is not None
            and baseline.get("log_loss") is not None
            and candidate["log_loss"] <= baseline["log_loss"]
        )
        return {
            "version": self.VERSION,
            "state": "EVALUATED",
            "samples": len(rows),
            "train_samples": self.min_train,
            "test_samples": len(raw_rows),
            "window_count": len(windows),
            "windows": windows,
            "baseline": baseline,
            "candidate": candidate,
            "candidate_pass": passed,
            "live_adjustment": False,
        }
