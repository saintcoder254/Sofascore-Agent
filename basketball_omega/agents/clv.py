from basketball_omega.contracts import AgentOpinion

class CLVAgent:
    name="clv-ledger"
    def run(self,market):
        entry=market.get("entry_spread"); close=market.get("closing_spread"); fair=market.get("fair_spread")
        if entry is None or close is None:return AgentOpinion(self.name,"CLV_PENDING",0.0,risks=["Entry/closing line pair unavailable."])
        clv=float(entry)-float(close)
        return AgentOpinion(self.name,"CLV_RECORDED",.9,evidence={"entry_spread":entry,"closing_spread":close,"fair_spread":fair,"clv_points":clv},rationale=["Closing-line value is recorded independently of match outcome."])
