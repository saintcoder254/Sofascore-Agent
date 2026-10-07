"""OMEGA Out-of-Sample Model Tournament v4.

Chronological expanding-window walk-forward evaluation with explicit
market-specific grouping. A model cannot become production-eligible merely
because a pooled holdout looks good.
"""
from collections import defaultdict
from calibration_engine import CalibrationEngine


class OOSModelTournament:
    VERSION = "OMEGA-OOS-TOURNAMENT-v4-WALKFORWARD-MARKET"

    def __init__(self, min_train=175, min_test=250, min_windows=2):
        self.min_train = max(175, int(min_train))
        self.min_test = max(250, int(min_test))
        self.min_windows = max(2, int(min_windows))
        self.cal = CalibrationEngine()

    @staticmethod
    def _key(row):
        return (str(row.get("fixture_id")), str(row.get("market")))

    @staticmethod
    def _market(row):
        return str(row.get("market") or "UNKNOWN")

    def _ordered(self, rows):
        return sorted(
            [
                r for r in rows
                if r.get("predicted_at") is not None
                and r.get("fixture_id") is not None
                and r.get("market") is not None
                and r.get("p") is not None
                and r.get("y") is not None
            ],
            key=lambda x: (float(x["predicted_at"]), self._key(x)),
        )

    def _windows(self, rows):
        """Expanding train / forward test windows; no future rows enter a train set."""
        ordered = self._ordered(rows)
        out = []
        train_end = self.min_train
        while train_end + self.min_test <= len(ordered):
            test_end = train_end + self.min_test
            train = ordered[:train_end]
            test = ordered[train_end:test_end]
            out.append({
                "window": len(out) + 1,
                "train_end_index": train_end,
                "test_end_index": test_end,
                "train_samples": len(train),
                "test_samples": len(test),
                "test_start": float(test[0]["predicted_at"]),
                "test_end": float(test[-1]["predicted_at"]),
                "metrics": self.cal.evaluate(test),
            })
            train_end = test_end
        return out

    def _evaluate_market(self, rows):
        windows = self._windows(rows)
        evaluated = len(windows) >= self.min_windows and all(
            w["test_samples"] >= self.min_test for w in windows
        )
        test_rows = []
        for w in windows:
            # Rebuild the exact chronological test slices for aggregate metrics.
            ordered = self._ordered(rows)
            test_rows.extend(ordered[w["train_end_index"]:w["test_end_index"]])
        metrics = self.cal.evaluate(test_rows) if evaluated else None
        return {
            "state": "EVALUATED" if evaluated else "SHADOW",
            "windows": windows,
            "window_count": len(windows),
            "samples": len(rows),
            "test_samples": len(test_rows),
            "metrics": metrics,
            "walk_forward_pass": bool(
                evaluated
                and metrics
                and metrics.get("log_loss") is not None
                and metrics.get("brier") is not None
            ),
        }

    def run(self, models):
        prepared = {name: self._ordered(rows) for name, rows in models.items()}

        # Every market is evaluated independently. A pooled football/basketball or
        # pooled multi-market result can never satisfy a market-specific gate.
        market_results = {}
        promotion_ready = []
        for model_name, rows in prepared.items():
            by_market = defaultdict(list)
            for row in rows:
                by_market[self._market(row)].append(row)
            market_results.setdefault(model_name, {})
            for market, market_rows in sorted(by_market.items()):
                result = self._evaluate_market(market_rows)
                market_results[model_name][market] = result
                if result["walk_forward_pass"]:
                    promotion_ready.append({"model": model_name, "market": market})

        # Backward-compatible model summary, but it is informational only.
        model_summary = {}
        for model_name, rows in prepared.items():
            all_windows = self._windows(rows)
            evaluated = len(all_windows) >= self.min_windows
            test_rows = []
            ordered = rows
            for w in all_windows:
                test_rows.extend(ordered[w["train_end_index"]:w["test_end_index"]])
            model_summary[model_name] = {
                "samples": len(rows),
                "train_samples": self.min_train if rows else 0,
                "test_samples": len(test_rows),
                "state": "EVALUATED" if evaluated else "SHADOW",
                "metrics": self.cal.evaluate(test_rows) if evaluated else None,
                "market_specific_required": True,
            }

        return {
            "version": self.VERSION,
            "min_train": self.min_train,
            "min_test": self.min_test,
            "min_windows": self.min_windows,
            "models": model_summary,
            "market_results": market_results,
            "promotion_ready_models": promotion_ready,
            "promotion_ready": bool(promotion_ready),
            "promotion": "NONE_UNTIL_WALK_FORWARD_AND_MARKET_BENCHMARK",
        }
