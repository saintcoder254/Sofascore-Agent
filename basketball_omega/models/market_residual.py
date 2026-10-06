"""Market-residual modeling for basketball OOS evaluation.

The market is treated as a strong prior. The model is rewarded only for
residual information beyond that prior, not for reproducing the market.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class ResidualEstimate:
    market_margin: float
    model_margin: float
    residual: float
    blended_margin: float
    edge_points: float
    confidence: float

class MarketResidualEngine:
    def __init__(self, model_weight: float = 0.35):
        self.model_weight=max(0.0,min(1.0,float(model_weight)))

    def estimate(self, model_margin: float, opening_spread: float | None):
        if opening_spread is None:
            return ResidualEstimate(0.0,float(model_margin),float(model_margin),
                                    float(model_margin),0.0,0.0)
        market=-float(opening_spread)
        residual=float(model_margin)-market
        blended=market+self.model_weight*residual
        confidence=min(1.0,abs(residual)/8.0)
        return ResidualEstimate(market,float(model_margin),residual,blended,residual,confidence)

    @staticmethod
    def probability(margin: float, scale: float = 7.0):
        z=max(-35.0,min(35.0,float(margin)/scale))
        return 1.0/(1.0+math.exp(-z))
