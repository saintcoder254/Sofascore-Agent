"""OMEGA evidence promotion gate.

Promotion is market-specific. A model is not production-eligible unless the
same model/market pair has chronological walk-forward evidence and verified
positive CLV/market-benchmark evidence.
"""


class OmegaPromotionGate:
    VERSION = "OMEGA-PROMOTION-GATE-v3-STRICT-OOS-CLV"

    def __init__(self, min_samples=250, min_clv_samples=50):
        self.min_samples = max(250, int(min_samples))
        self.min_clv_samples = max(50, int(min_clv_samples))

    def evaluate(self, ledger, integrity, calibration, weights, market_benchmark, oos=None):
        reasons = []
        n = len(ledger)
        if n < self.min_samples:
            reasons.append("INSUFFICIENT_LEDGER_SAMPLES")
        if not integrity or not all(bool(x.get("valid")) for x in integrity):
            reasons.append("LEDGER_INTEGRITY_FAILURE")
        if calibration.get("state") != "EVALUATED" or not calibration.get("candidate_pass"):
            reasons.append("CALIBRATION_GATE_NOT_PASSED")
        earned = {str(x.get("model")) for x in weights.get("models", []) if x.get("status") == "EARNED"}
        if not earned:
            reasons.append("NO_EARNED_MODEL")

        if not oos or oos.get("state") not in {"EVALUATED", "PASS"} or not oos.get("promotion_ready"):
            reasons.append("OOS_WALK_FORWARD_GATE_NOT_PASSED")
        else:
            ready_pairs = {
                (str(x.get("model")), str(x.get("market")))
                for x in oos.get("promotion_ready_models", [])
            }
            if not any(model in earned for model, _ in ready_pairs):
                reasons.append("NO_EARNED_MODEL_WITH_MARKET_SPECIFIC_OOS")

        clv_n = int(market_benchmark.get("clv_available") or 0)
        avg_clv = float(market_benchmark.get("avg_clv") or 0)
        if clv_n < self.min_clv_samples:
            reasons.append("INSUFFICIENT_VERIFIED_CLV_SAMPLES")
        elif avg_clv <= 0:
            reasons.append("MARKET_BENCHMARK_CLV_NOT_POSITIVE")
        if market_benchmark.get("state") == "FAILED":
            reasons.append("MARKET_BENCHMARK_FAILED")

        # Require at least one OOS-ready market to also have sufficient positive CLV.
        by_market = market_benchmark.get("by_market") or {}
        if oos and oos.get("promotion_ready"):
            ready_markets = {str(x.get("market")) for x in oos.get("promotion_ready_models", []) if str(x.get("model")) in earned}
            benchmark_ready = [
                m for m in ready_markets
                if (by_market.get(m) or {}).get("clv_available", 0) >= self.min_clv_samples
                and float((by_market.get(m) or {}).get("avg_clv") or 0) > 0
            ]
            if not benchmark_ready:
                reasons.append("NO_MARKET_SPECIFIC_POSITIVE_CLV_FOR_OOS_MODEL")

        return {
            "version": self.VERSION,
            "state": "PROMOTE" if not reasons else "SHADOW",
            "enabled": not reasons,
            "samples": n,
            "reasons": reasons,
            "clv_samples": clv_n,
            "oos_ready_pairs": sorted([{"model": m, "market": k} for m, k in (
                {(str(x.get("model")), str(x.get("market"))) for x in (oos or {}).get("promotion_ready_models", [])}
            )]),
        }
