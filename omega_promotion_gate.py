"""OMEGA evidence promotion gate."""

class OmegaPromotionGate:
    VERSION = "OMEGA-PROMOTION-GATE-v2-STRICT-CLV"

    def __init__(self, min_samples=250, min_clv_samples=50):
        self.min_samples = max(250, int(min_samples))
        self.min_clv_samples = max(50, int(min_clv_samples))

    def evaluate(self, ledger, integrity, calibration, weights, market_benchmark):
        reasons = []
        n = len(ledger)
        if n < self.min_samples:
            reasons.append("INSUFFICIENT_LEDGER_SAMPLES")
        if not integrity or not all(bool(x.get("valid")) for x in integrity):
            reasons.append("LEDGER_INTEGRITY_FAILURE")
        if calibration.get("state") != "EVALUATED" or not calibration.get("candidate_pass"):
            reasons.append("CALIBRATION_GATE_NOT_PASSED")
        if not any(x.get("status") == "EARNED" for x in weights.get("models", [])):
            reasons.append("NO_EARNED_MODEL")
        clv_n = int(market_benchmark.get("clv_available") or 0)
        avg_clv = float(market_benchmark.get("avg_clv") or 0)
        # CLV is a production-evidence requirement, not an optional bonus.
        # Absence of enough verified closing-line observations cannot be
        # interpreted as neutral evidence.
        if clv_n < self.min_clv_samples:
            reasons.append("INSUFFICIENT_VERIFIED_CLV_SAMPLES")
        elif avg_clv <= 0:
            reasons.append("MARKET_BENCHMARK_CLV_NOT_POSITIVE")
        if market_benchmark.get("state") == "FAILED":
            reasons.append("MARKET_BENCHMARK_FAILED")
        return {
            "version": self.VERSION,
            "state": "PROMOTE" if not reasons else "SHADOW",
            "enabled": not reasons,
            "samples": n,
            "reasons": reasons,
            "clv_samples": clv_n,
        }
