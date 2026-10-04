"""OMEGA Market Benchmark Engine v1.

Treats the betting market as an adversarial benchmark rather than a signal to
blindly copy. Stores opening/current/closing observations and computes CLV.
"""
import math

class MarketBenchmarkEngine:
    VERSION="OMEGA-MARKET-BENCHMARK-v1"

    @staticmethod
    def implied(odds):
        try:
            o=float(odds); return 1/o if o>1 else None
        except (TypeError,ValueError):return None

    @staticmethod
    def clv(decision_odds,closing_odds):
        try:
            d=float(decision_odds); c=float(closing_odds)
            if d<=1 or c<=1:return None
            # Positive when the bettor obtained a better price than close.
            return c/d-1.0
        except (TypeError,ValueError):return None

    def evaluate(self,decision):
        odds=decision.get("odds"); close=decision.get("closing_odds")
        return {"version":self.VERSION,"decision_implied":self.implied(odds),"closing_implied":self.implied(close),"clv":self.clv(odds,close),"available":odds is not None and close is not None}
