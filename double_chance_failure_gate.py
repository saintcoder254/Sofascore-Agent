"""Double-chance failure gate v1.

Specifically targets X2/1X/DNB protection bets. A protected side must survive
an explicit adverse home/away branch, price/value gate, and regime-sensitivity
test. Missing stress evidence produces SHADOW rather than confidence inflation.
"""
class DoubleChanceFailureGate:
    VERSION="OMEGA-DC-FAILURE-GATE-v1"
    MARKETS={"DOUBLE_CHANCE","DNB","1X2"}

    def __init__(self,min_p=0.60,min_edge=0.03):
        self.min_p=float(min_p); self.min_edge=float(min_edge)

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    def evaluate(self,candidate,evidence=None):
        evidence=evidence or {}
        market=str(candidate.get("market") or "").upper()
        selection=str(candidate.get("selection") or "").upper()
        if market not in self.MARKETS or selection not in {"X2","1X","2","1","AWAY","HOME"}:
            return {"version":self.VERSION,"state":"NOT_APPLICABLE","blockers":[],"warnings":[]}
        if market=="1X2": return {"version":self.VERSION,"state":"NOT_APPLICABLE","blockers":[],"warnings":[]}
        p=self._num(candidate.get("model_probability"))
        odds=self._num(candidate.get("odds"))
        edge=self._num(candidate.get("edge"))
        blockers=[]; warnings=[]
        if p is None or odds is None: blockers.append("DC_MISSING_PROBABILITY_OR_PRICE")
        elif p*odds-1.0 <= 0: blockers.append("DC_NO_POSITIVE_EV")
        if edge is not None and edge < self.min_edge: blockers.append("DC_EDGE_BELOW_MINIMUM")
        stress=evidence.get("double_chance_stress") or {}
        adverse=self._num(stress.get("adverse_branch_probability"))
        if adverse is None: blockers.append("DC_ADVERSE_BRANCH_NOT_TESTED")
        elif adverse < 0.20: warnings.append("DC_ADVERSE_BRANCH_TOO_LOW")
        else:
            if stress.get("adverse_branch_market") not in {"home_win","away_win","draw"}:
                blockers.append("DC_ADVERSE_BRANCH_INVALID")
        sensitivity=self._num(stress.get("probability_sensitivity"))
        if sensitivity is None: blockers.append("DC_SENSITIVITY_NOT_TESTED")
        elif sensitivity > 0.10: blockers.append("DC_REGIME_SENSITIVITY_HIGH")
        market_confirmed=stress.get("market_confirmed")
        if market_confirmed is not True: warnings.append("DC_MARKET_CONFIRMATION_MISSING")
        return {"version":self.VERSION,"state":"BLOCK" if blockers else ("CAUTION" if warnings else "PASS"),"blockers":blockers,"warnings":warnings,
                "inputs":{"probability":p,"odds":odds,"edge":edge,"adverse_branch_probability":adverse,"probability_sensitivity":sensitivity,"market_confirmed":market_confirmed}}

