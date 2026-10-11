"""OMEGA calibration and model-health metrics.

Metrics are computed only from finite, in-range probability/outcome pairs.
The engine supports binary one-vs-rest outcomes and soft labels in [0, 1].
"""
import math
from collections import defaultdict


class CalibrationEngine:
    VERSION = "OMEGA-CALIBRATION-v2"

    @staticmethod
    def _valid_rows(rows):
        valid = []
        invalid = 0
        for row in rows or []:
            try:
                p = float(row["p"])
                y = float(row["y"])
            except (KeyError, TypeError, ValueError, OverflowError):
                invalid += 1
                continue
            if not math.isfinite(p) or not math.isfinite(y) or not (0.0 <= p <= 1.0) or not (0.0 <= y <= 1.0):
                invalid += 1
                continue
            valid.append({"p": p, "y": y})
        return valid, invalid

    @classmethod
    def brier(cls, rows):
        vals, _ = cls._valid_rows(rows)
        return sum((r["p"] - r["y"]) ** 2 for r in vals) / len(vals) if vals else None

    @classmethod
    def log_loss(cls, rows):
        vals, _ = cls._valid_rows(rows)
        if not vals:
            return None
        eps = 1e-15
        total = 0.0
        for r in vals:
            p = min(1.0 - eps, max(eps, r["p"]))
            y = r["y"]
            total += -y * math.log(p) - (1.0 - y) * math.log(1.0 - p)
        return total / len(vals)

    @classmethod
    def reliability(cls, rows, bins=None):
        vals, _ = cls._valid_rows(rows)
        if bins is None:
            bins = [i / 10 for i in range(11)]
        out = []
        for i, (lo, hi) in enumerate(zip(bins[:-1], bins[1:])):
            # Include p=1.0 in the final bin; other bins are half-open.
            selected = [r for r in vals if lo <= r["p"] < hi or (i == len(bins) - 2 and r["p"] == hi)]
            if not selected:
                continue
            actual = sum(r["y"] for r in selected) / len(selected)
            predicted = sum(r["p"] for r in selected) / len(selected)
            out.append({
                "low": lo, "high": hi, "samples": len(selected),
                "predicted": predicted, "actual": actual, "gap": actual - predicted,
            })
        return out

    def evaluate(self, rows):
        vals, invalid = self._valid_rows(rows)
        rel = self.reliability(vals)
        total = sum(x["samples"] for x in rel)
        ece = sum((x["samples"] / total) * abs(x["gap"]) for x in rel) if total else None
        return {
            "version": self.VERSION,
            "samples": len(vals),
            "invalid_rows": invalid,
            "brier": self.brier(vals),
            "log_loss": self.log_loss(vals),
            "ece": ece,
            "reliability": rel,
        }

    def compare_models(self, ledger):
        groups = defaultdict(list)
        for row in ledger or []:
            groups[str(row.get("model") or "unknown")].append(row)
        out = []
        for model, rows in groups.items():
            out.append({"model": model, **self.evaluate(rows)})
        return sorted(out, key=lambda x: (x["log_loss"] is None, x["log_loss"] or 999))


class ModelHealthEngine:
    VERSION = "OMEGA-MODEL-HEALTH-v1"

    def assess(self, metrics):
        flags = []
        if metrics.get("ece") is not None and metrics["ece"] > 0.08:
            flags.append("CALIBRATION_DRIFT")
        if metrics.get("brier") is not None and metrics["brier"] > 0.25:
            flags.append("WEAK_PROBABILITY_QUALITY")
        if metrics.get("samples", 0) == 0:
            flags.append("NO_VALIDATION_SAMPLES")
        if metrics.get("invalid_rows", 0):
            flags.append("INVALID_VALIDATION_ROWS")
        return {"version": self.VERSION, "state": "DEGRADED" if flags else "HEALTHY", "flags": flags}
