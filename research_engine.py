import json
import math
import time
import urllib.request
from collections import defaultdict


class ResearchEngine:
    """Research + experiment layer for controlled MatchMaster evolution.

    This module is intentionally deterministic and dependency-light. It can
    discover public technology updates, generate feature hypotheses from the
    recorded experience store, and evaluate candidates without changing the
    production model.
    """

    def __init__(self, store):
        self.store = store

    def feature_inventory(self):
        rows = self.store.predictions_with_outcomes()
        keys = defaultdict(int)
        for row in rows:
            for key in row.get("features", {}) or {}:
                keys[key] += 1
        return sorted(keys.items(), key=lambda x: (-x[1], x[0]))

    def hypotheses(self):
        inventory = self.feature_inventory()
        hypotheses = []
        for key, count in inventory:
            if count >= 20:
                hypotheses.append({
                    "type": "feature_interaction",
                    "feature": key,
                    "evidence": count,
                    "hypothesis": f"Evaluate whether {key} improves probability calibration or market discrimination.",
                    "status": "EXPERIMENT_REQUIRED",
                })
        hypotheses.append({
            "type": "calibration",
            "feature": None,
            "evidence": self.store.resolved_prediction_count(),
            "hypothesis": "Compare raw probabilities with probability-bucket calibration using walk-forward validation.",
            "status": "EXPERIMENT_REQUIRED",
        })
        return hypotheses

    @staticmethod
    def _clip(p):
        return min(max(float(p), 1e-6), 1 - 1e-6)

    @classmethod
    def brier(cls, rows, probability_key="predicted_probability"):
        if not rows:
            return None
        return sum((float(r[probability_key]) - float(r["outcome"])) ** 2 for r in rows) / len(rows)

    @classmethod
    def log_loss(cls, rows, probability_key="predicted_probability"):
        if not rows:
            return None
        total = 0.0
        for r in rows:
            p = cls._clip(r[probability_key])
            y = float(r["outcome"])
            total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        return total / len(rows)

    @staticmethod
    def _calibration_map(training):
        buckets = {i: [0, 0] for i in range(10)}
        for r in training:
            b = min(9, max(0, int(float(r["predicted_probability"]) * 10)))
            buckets[b][0] += 1
            buckets[b][1] += float(r["outcome"])
        return {
            b: (s + 0.5) / (n + 1.0)
            for b, (n, s) in buckets.items()
            if n >= 5
        }

    @staticmethod
    def _apply_calibration(row, mapping):
        p = float(row["predicted_probability"])
        b = min(9, max(0, int(p * 10)))
        clone = dict(row)
        clone["predicted_probability"] = mapping.get(b, p)
        return clone

    def walk_forward_calibration(self, min_train=30, min_test=10):
        rows = sorted(self.store.predictions_with_outcomes(), key=lambda r: r["predicted_at"])
        if len(rows) < min_train + min_test:
            return {
                "status": "INSUFFICIENT_DATA",
                "samples": len(rows),
                "minimum": min_train + min_test,
            }

        split = max(min_train, int(len(rows) * 0.7))
        training, test = rows[:split], rows[split:]
        mapping = self._calibration_map(training)
        calibrated = [self._apply_calibration(r, mapping) for r in test]
        raw_brier = self.brier(test)
        calibrated_brier = self.brier(calibrated)
        raw_log = self.log_loss(test)
        calibrated_log = self.log_loss(calibrated)
        improvement = (raw_brier - calibrated_brier) if raw_brier is not None else 0.0
        return {
            "status": "EVALUATED",
            "train_samples": len(training),
            "test_samples": len(test),
            "baseline_brier": round(raw_brier, 6),
            "candidate_brier": round(calibrated_brier, 6),
            "baseline_log_loss": round(raw_log, 6),
            "candidate_log_loss": round(calibrated_log, 6),
            "brier_improvement": round(improvement, 6),
            "candidate_pass": bool(improvement > 0 and calibrated_log <= raw_log),
        }

    def technology_scout(self):
        """Read lightweight public release metadata without executing remote code."""
        targets = {
            "curl_cffi": "https://pypi.org/pypi/curl-cffi/json",
            "scikit-learn": "https://pypi.org/pypi/scikit-learn/json",
            "pandas": "https://pypi.org/pypi/pandas/json",
        }
        findings = []
        for package, url in targets.items():
            try:
                request = urllib.request.Request(
                    url,
                    headers={"User-Agent": "EliteMatchMaster-Evolution-Core/1.0"},
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                info = payload.get("info", {})
                findings.append({
                    "package": package,
                    "latest_version": info.get("version"),
                    "project_url": info.get("project_url"),
                    "checked_at": time.time(),
                    "status": "DISCOVERED",
                })
            except Exception as exc:
                findings.append({
                    "package": package,
                    "status": "UNAVAILABLE",
                    "error": repr(exc),
                    "checked_at": time.time(),
                })
        return findings

    def research_report(self):
        return {
            "agent": "Evolution Research Engine",
            "generated_at": time.time(),
            "feature_inventory": self.feature_inventory(),
            "hypotheses": self.hypotheses(),
            "walk_forward": self.walk_forward_calibration(),
            "technology": self.technology_scout(),
        }
