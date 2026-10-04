"""OMEGA League Intelligence Engine v1.

Ranks competitions from settled, point-in-time prediction records. This is a
diagnostic/selection layer: it does not alter live model probabilities.

The score deliberately separates data depth, calibration quality, realized
value, market benchmark quality, and coverage. Low-sample leagues are shrunk
toward a neutral score and are marked PROVISIONAL rather than being treated
as proven edges.
"""
import math
from collections import defaultdict

class LeagueIntelligenceEngine:
    VERSION = "OMEGA-LEAGUE-INTELLIGENCE-v1"

    def __init__(self, min_samples=30, proven_samples=100):
        self.min_samples = max(10, int(min_samples))
        self.proven_samples = max(self.min_samples, int(proven_samples))

    @staticmethod
    def _num(v):
        try:
            x = float(v)
            return x if math.isfinite(x) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _mean(values):
        return sum(values) / len(values) if values else None

    def _competition(self, row):
        features = row.get("features") or {}
        return (features.get("competition")
                or features.get("league")
                or features.get("tournament")
                or "UNKNOWN")

    def _row_metrics(self, rows):
        n = len(rows)
        brier = self._mean([
            (float(r["predicted_probability"]) - float(r["outcome"])) ** 2
            for r in rows
            if r.get("predicted_probability") is not None and r.get("outcome") is not None
        ])
        logloss = self._mean([
            -float(r["outcome"]) * math.log(max(1e-12, min(1 - 1e-12, float(r["predicted_probability"]))))
            - (1 - float(r["outcome"])) * math.log(max(1e-12, min(1 - 1e-12, 1 - float(r["predicted_probability"]))))
            for r in rows
            if r.get("predicted_probability") is not None and r.get("outcome") is not None
        ])

        odds_rows = [r for r in rows if self._num(r.get("odds")) and self._num(r.get("odds")) > 1]
        profit = 0.0
        for r in odds_rows:
            o = float(r["odds"])
            y = float(r["outcome"])
            profit += (o - 1.0) if y == 1.0 else (-1.0 if y == 0.0 else 0.0)
        roi = profit / len(odds_rows) if odds_rows else None

        evs = []
        positive_ev = 0
        for r in odds_rows:
            p = self._num(r.get("predicted_probability"))
            if p is None:
                continue
            ev = p * float(r["odds"]) - 1.0
            evs.append(ev)
            positive_ev += int(ev > 0)

        clv_rows = []
        for r in rows:
            d = self._num(r.get("odds"))
            c = self._num(r.get("closing_odds"))
            if d and c and d > 1 and c > 1:
                clv_rows.append(d / c - 1.0)

        markets = sorted({str(r.get("market") or "UNKNOWN") for r in rows})
        avg_p = self._mean([float(r["predicted_probability"]) for r in rows if r.get("predicted_probability") is not None])
        actual = self._mean([float(r["outcome"]) for r in rows if r.get("outcome") is not None])

        return {
            "samples": n,
            "brier": brier,
            "log_loss": logloss,
            "roi": roi,
            "avg_expected_value": self._mean(evs),
            "positive_ev_rate": (positive_ev / len(evs)) if evs else None,
            "clv_samples": len(clv_rows),
            "avg_clv": self._mean(clv_rows),
            "positive_clv_rate": (sum(x > 0 for x in clv_rows) / len(clv_rows)) if clv_rows else None,
            "markets": markets,
            "market_count": len(markets),
            "avg_probability": avg_p,
            "actual_rate": actual,
            "calibration_gap": None if avg_p is None or actual is None else actual - avg_p,
        }

    @staticmethod
    def _bounded(x, lo, hi):
        return max(lo, min(hi, x))

    def _score(self, m):
        n = m["samples"]
        data_score = 20.0 * self._bounded(math.log1p(n) / math.log1p(self.proven_samples), 0, 1)

        bq = 1.0 - self._bounded((m["brier"] or 0.25) / 0.25, 0, 1)
        lq = 1.0 - self._bounded((m["log_loss"] or math.log(2)) / math.log(2), 0, 1)
        calibration_score = 25.0 * (0.5 * bq + 0.5 * lq)

        roi = self._bounded((m["roi"] if m["roi"] is not None else 0.0) / 0.20, -1, 1)
        evr = m["positive_ev_rate"] if m["positive_ev_rate"] is not None else 0.5
        value_score = 25.0 * (0.55 * ((roi + 1) / 2) + 0.45 * evr)

        if m["clv_samples"]:
            clv = self._bounded((m["avg_clv"] or 0.0) / 0.10, -1, 1)
            clv_score = 15.0 * (0.55 * ((clv + 1) / 2) + 0.45 * m["positive_clv_rate"])
        else:
            clv_score = 7.5

        coverage_score = 15.0 * self._bounded(m["market_count"] / 6.0, 0, 1)
        raw = data_score + calibration_score + value_score + clv_score + coverage_score

        shrink = min(1.0, n / float(self.proven_samples))
        score = 50.0 + shrink * (raw - 50.0)

        if n >= self.proven_samples:
            status = "PROVEN_CANDIDATE"
        elif n < self.min_samples:
            status = "INSUFFICIENT_SAMPLE"
        else:
            status = "PROVISIONAL"

        return round(self._bounded(score, 0, 100), 2), status

    def rank(self, predictions):
        groups = defaultdict(list)
        for row in predictions or []:
            comp = self._competition(row)
            if comp != "UNKNOWN":
                groups[comp].append(row)

        ranked = []
        for competition, rows in groups.items():
            metrics = self._row_metrics(rows)
            score, status = self._score(metrics)
            ranked.append({
                "competition": competition,
                "league_score": score,
                "status": status,
                **metrics,
            })

        ranked.sort(key=lambda x: (-x["league_score"], -x["samples"], x["competition"]))
        for i, row in enumerate(ranked, 1):
            row["rank"] = i

        return {
            "version": self.VERSION,
            "minimum_samples": self.min_samples,
            "proven_samples": self.proven_samples,
            "ranking": ranked,
            "methodology": {
                "data_depth": 20,
                "calibration": 25,
                "realized_value": 25,
                "market_benchmark": 15,
                "market_coverage": 15,
                "low_sample_shrinkage": "Scores shrink toward 50 until proven_samples are reached.",
                "promotion_rule": "League ranking is diagnostic; it never directly changes live probabilities.",
            },
        }

    def detail(self, predictions, competition):
        report = self.rank(predictions)
        for row in report["ranking"]:
            if str(row["competition"]).casefold() == str(competition).casefold():
                return row
        return None
