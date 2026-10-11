from basketball_omega.contracts import BasketballContext, AgentOpinion

class MarketResidualAgent:
    name="market-residual"
    def run(self,ctx:BasketballContext)->AgentOpinion:
        m=ctx.market; line=m.get("spread"); total=m.get("total"); model_margin=m.get("model_margin"); model_total=m.get("model_total")
        fair_margin=float(model_margin) if model_margin is not None else None
        fair_total=float(model_total) if model_total is not None else None
        rationale=["Market is treated as a benchmark and residual target, not as ground truth."]
        if line is not None and fair_margin is not None:rationale.append("Spread residual is measured from model fair value to current market line.")
        return AgentOpinion(self.name,"MARKET_RESIDUAL",.75,fair_margin=fair_margin,fair_total=fair_total,rationale=rationale,evidence={"spread":line,"total":total,"spread_residual":(fair_margin-float(line)) if line is not None and fair_margin is not None else None,"total_residual":(fair_total-float(total)) if total is not None and fair_total is not None else None})
