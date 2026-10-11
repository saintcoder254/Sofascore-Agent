"""Hard routing boundary for basketball.

The router accepts only basketball contexts and never dispatches to football
UMIOS probability/market code. This is deliberately a small policy layer.
"""
from basketball_omega.contracts import BasketballContext, FusionVerdict
from basketball_omega.orchestrator import BasketballOmegaOrchestrator

class BasketballRouter:
    SPORT = "basketball"

    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator or BasketballOmegaOrchestrator()

    def analyze(self, ctx: BasketballContext) -> FusionVerdict:
        if not isinstance(ctx, BasketballContext):
            raise TypeError("basketball router accepts BasketballContext only")
        return self.orchestrator.run(ctx)
