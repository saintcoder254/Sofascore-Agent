import json
import math
import statistics
import time
import uuid
from collections import defaultdict


class EvolutionAgent:
    """Controlled self-improvement engine for Elite MatchMaster.

    It learns from recorded predictions/outcomes, recalibrates probabilities,
    detects drift, and creates candidate improvements. It never overwrites the
    production model directly; promotion is explicitly gated.
    """

    def __init__(self, store, min_samples=100):
        self.store = store
        self.min_samples = max(20, int(min_samples))

    @staticmethod
    def _clip_probability(p):
        return min(max(float(p), 1e-6), 1 - 1e-6)

    @staticmethod
    def brier(prob, outcome):
        return (float(prob) - float(outcome)) ** 2

    @classmethod
    def log_loss(cls, prob, outcome):
        p = cls._clip_probability(prob)
        y = float(outcome)
        return -(y * math.log(p) + (1 - y) * math.log(1 - p))

    @staticmethod
    def _bucket(prob, buckets=10):
        return min(buckets - 1, max(0, int(float(prob) * buckets)))

    def train_bucket_calibrator(self, rows):
        """Online-friendly beta-smoothed calibration by probability bucket."""
        stats = {i: {"n": 0, "successes": 0} for i in range(10)}
        for row in rows:
            if row.get("outcome") is None:
                continue
            b = self._bucket(row["predicted_probability"])
            stats[b]["n"] += 1
            stats[b]["successes"] += int(row["outcome"])

        calibration = {}
        for bucket, s in stats.items():
            # Jeffreys-style Beta(1/2, 1/2) smoothing prevents extreme 0/1 outputs.
            calibration[str(bucket)] = {
                "samples": s["n"],
                "rate": round((s["successes"] + 0.5) / (s["n"] + 1.0), 6),
            }
        return calibration

    def calibrate_probability(self, probability, calibration):
        bucket = str(self._bucket(probability))
        item = calibration.get(bucket)
        if not item or item.get("samples", 0) < 5:
            return float(probability)
        return float(item["rate"])

    def _metrics(self, rows):
        resolved = [r for r in rows if r.get("outcome") is not None]
        if not resolved:
            return {"samples": 0, "brier": None, "log_loss": None, "accuracy": None}
        briers = [self.brier(r["predicted_probability"], r["outcome"]) for r in resolved]
        losses = [self.log_loss(r["predicted_probability"], r["outcome"]) for r in resolved]
        accuracy = sum(
            int((r["predicted_probability"] >= 0.5) == bool(r["outcome"]))
            for r in resolved
        ) / len(resolved)
        return {
            "samples": len(resolved),
            "brier": round(statistics.fmean(briers), 6),
            "log_loss": round(statistics.fmean(losses), 6),
            "accuracy": round(accuracy, 6),
        }

    def _group(self, rows, key):
        groups = defaultdict(list)
        for row in rows:
            groups[row.get(key, "unknown")].append(row)
        return groups

    def run_cycle(self, reason="scheduled"):
        rows = self.store.predictions_with_outcomes()
        metrics = self._metrics(rows)
        cycle_id = str(uuid.uuid4())
        result = {
            "cycle_id": cycle_id,
            "reason": reason,
            "created_at": time.time(),
            "baseline": metrics,
            "groups": {},
            "calibration": {},
            "candidates": [],
            "status": "INSUFFICIENT_DATA" if metrics["samples"] < self.min_samples else "EVALUATED",
        }

        if metrics["samples"]:
            result["calibration"] = self.train_bucket_calibrator(rows)

        for market, market_rows in self._group(rows, "market").items():
            m = self._metrics(market_rows)
            result["groups"][market] = m
            if m["samples"] >= self.min_samples:
                candidate = {
                    "candidate_id": str(uuid.uuid4()),
                    "type": "probability_calibration",
                    "market": market,
                    "description": "Apply beta-smoothed probability-bucket calibration before market selection.",
                    "evidence_samples": m["samples"],
                    "status": "SHADOW_TEST_REQUIRED",
                    "created_at": time.time(),
                }
                result["candidates"].append(candidate)
                self.store.add_candidate(candidate)

        self.store.add_evolution_run(cycle_id, result)
        return result

    def status(self):
        return {
            "agent": "Elite MatchMaster Evolution Core",
            "version": "1.0.0",
            "mode": "controlled_autonomous",
            "min_samples": self.min_samples,
            "prediction_count": self.store.prediction_count(),
            "resolved_count": self.store.resolved_prediction_count(),
            "latest_run": self.store.latest_evolution_run(),
            "latest_candidates": self.store.latest_candidates(20),
        }
