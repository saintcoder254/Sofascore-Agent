"""Universal market validation/calibration firewall.

The historical class name is retained for compatibility, but Final Arbiter now
uses the universal validator for every market segment.
"""
from __future__ import annotations
import math

class MarketValidationGate:
    VERSION="OMEGA-UMQE-v1"
    ALL_MARKETS={"1X2","DOUBLE_CHANCE","DNB","BTTS","TOTAL_GOALS","TEAM_GOALS","TEAM_TOTAL","HANDICAP","CORNERS","CARDS","CORRECT_SCORE","HT","HALF_TIME","HT_FT","HTFT"}
    MIN_SAMPLES={"1X2":30,"DOUBLE_CHANCE":30,"DNB":30,"BTTS":30,"TOTAL_GOALS":30,"TEAM_GOALS":30,"TEAM_TOTAL":30,"HANDICAP":30,"CORNERS":40,"CARDS":40,"CORRECT_SCORE":50,"HT":30,"HALF_TIME":30,"HT_FT":50,"HTFT":50}
    MAX_GAP={"1X2":.06,"DOUBLE_CHANCE":.05,"DNB":.05,"BTTS":.06,"TOTAL_GOALS":.06,"TEAM_GOALS":.06,"TEAM_TOTAL":.06,"HANDICAP":.06,"CORNERS":.08,"CARDS":.08,"CORRECT_SCORE":.05,"HT":.07,"HALF_TIME":.07,"HT_FT":.05,"HTFT":.05}
    MAX_SENS={"1X2":.08,"DOUBLE_CHANCE":.08,"DNB":.08,"BTTS":.08,"TOTAL_GOALS":.10,"TEAM_GOALS":.10,"TEAM_TOTAL":.10,"HANDICAP":.10,"CORNERS":.12,"CARDS":.12,"CORRECT_SCORE":.15,"HT":.10,"HALF_TIME":.10,"HT_FT":.15,"HTFT":.15}

    def __init__(self,store,min_samples=30):
        self.store=store; self.min_samples=max(30,int(min_samples))

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    @staticmethod
    def _market(v):
        s=str(v or "").upper().strip().replace(" ","_")
        return {"OVER_UNDER":"TOTAL_GOALS","GOALS_OU":"TOTAL_GOALS","TEAM_TOTAL":"TEAM_GOALS","HALF_TIME":"HT","HTFT":"HT_FT"}.get(s,s)

    @staticmethod
    def _band(odds):
        if odds is None:return "UNKNOWN"
        if odds<1.30:return "VERY_SHORT"
        if odds<1.50:return "SHORT"
        if odds<1.70:return "LOW"
        if odds<2.00:return "MEDIUM_LOW"
        if odds<3.00:return "MEDIUM"
        if odds<5.00:return "HIGH"
        return "LONG"

    @staticmethod
    def _wilson(wins,n):
        if n<=0:return 0.0
        z=1.959963984540054; phat=wins/n; den=1+z*z/n
        return (phat+z*z/(2*n)-z*math.sqrt((phat*(1-phat)+z*z/(4*n))/n))/den

    def evaluate(self,candidate,evidence=None,rows=None):
        evidence=evidence or {}; rows=list(rows if rows is not None else self.store.predictions_with_outcomes())
        market=self._market(candidate.get("market")); selection=str(candidate.get("selection") or "").upper()
        p=self._num(candidate.get("model_probability")); odds=self._num(candidate.get("odds"))
        blockers=[]; warnings=[]
        if market not in self.ALL_MARKETS:blockers.append("UMQE_UNSUPPORTED_MARKET")
        if p is None or odds is None or odds<=1:
            blockers.append("UMQE_MISSING_PROBABILITY_OR_PRICE")
            return self._result(market,selection,p,odds,[],[],blockers,warnings)
        eligible=[r for r in rows if str(r.get("model_version") or "").startswith("UMIOS-TITAN") and r.get("outcome") in (0,1,0.0,1.0) and self._num(r.get("predicted_probability")) is not None]
        band=self._band(odds)
        exact=[r for r in eligible if self._market(r.get("market"))==market and str(r.get("selection") or "").upper()==selection and self._band(self._num(r.get("odds")))==band]
        market_band=[r for r in eligible if self._market(r.get("market"))==market and self._band(self._num(r.get("odds")))==band]
        market_rows=[r for r in eligible if self._market(r.get("market"))==market]
        minimum=max(self.min_samples,self.MIN_SAMPLES.get(market,self.min_samples))
        if len(exact)<minimum:blockers.append("UMQE_CALIBRATION_SAMPLE_INSUFFICIENT")
        if not exact:return self._result(market,selection,p,odds,exact,market_band,blockers,warnings,price_band=band,market_samples=len(market_rows))
        avg=sum(float(r["predicted_probability"]) for r in exact)/len(exact)
        hit=sum(float(r["outcome"]) for r in exact)/len(exact)
        gap=abs(hit-avg); lower=self._wilson(sum(float(r["outcome"]) for r in exact),len(exact))
        if gap>self.MAX_GAP.get(market,.06):blockers.append("UMQE_CALIBRATION_GAP_TOO_LARGE")
        if p>.70 and lower<p-.08:blockers.append("UMQE_HIGH_PROBABILITY_NOT_SUPPORTED_BY_COHORT")
        if p>=.80 and lower<.70:blockers.append("UMQE_EXTREME_CONFIDENCE_UNSUPPORTED")
        stress=(evidence.get("market_stress") or evidence.get("double_chance_stress") or {})
        sensitivity=self._num(stress.get("probability_sensitivity"))
        if sensitivity is None:blockers.append("UMQE_STRESS_TEST_MISSING")
        elif abs(sensitivity)>self.MAX_SENS.get(market,.10):blockers.append("UMQE_REGIME_SENSITIVITY_TOO_HIGH")
        implied=1/odds
        if odds<1.50 and lower<max(implied+.02,.70):blockers.append("UMQE_SHORT_PRICE_BAND_UNRELIABLE")
        if odds<1.70 and (p*odds-1)<.07:blockers.append("UMQE_LOW_SHORT_PRICE_BUFFER")
        if (evidence.get("market_confirmed") is not True):blockers.append("UMQE_MARKET_CONFIRMATION_MISSING")
        calibrated=.70*p+.30*hit
        return self._result(market,selection,p,odds,exact,market_band,blockers,warnings,calibrated,hit,gap,lower,band,len(market_rows))

    @staticmethod
    def _result(market,selection,p,odds,exact,band_rows,blockers,warnings,calibrated=None,hit=None,gap=None,lower=None,price_band=None,market_samples=0):
        return {"version":MarketValidationGate.VERSION,"state":"BLOCK" if blockers else ("CAUTION" if warnings else "PASS"),"market":market,"selection":selection,"odds":odds,"raw_probability":p,"calibrated_probability":p if calibrated is None else calibrated,"calibration_samples":len(exact),"price_band_samples":len(band_rows),"market_samples":market_samples,"empirical_hit_rate":hit,"calibration_gap":gap,"wilson_lower_95":lower,"price_band":price_band,"blockers":blockers,"warnings":warnings}

class DoubleChanceFailureGate:
    VERSION="OMEGA-DC-FAILURE-GATE-v1"
    def __init__(self,min_p=0.60,min_edge=0.03): self.min_p=float(min_p); self.min_edge=float(min_edge)
    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None
    def evaluate(self,candidate,evidence=None):
        market=str(candidate.get("market") or "").upper()
        selection=str(candidate.get("selection") or "").upper()
        if market not in {"DOUBLE_CHANCE","DNB","1X2"} or selection not in {"X2","1X","2","1","AWAY","HOME"} or market=="1X2":
            return {"version":self.VERSION,"state":"NOT_APPLICABLE","blockers":[],"warnings":[]}
        evidence=evidence or {}; p=self._num(candidate.get("model_probability")); odds=self._num(candidate.get("odds")); edge=self._num(candidate.get("edge"))
        blockers=[]; warnings=[]; stress=evidence.get("double_chance_stress") or {}
        if p is None or odds is None:blockers.append("DC_MISSING_PROBABILITY_OR_PRICE")
        elif p*odds-1<=0:blockers.append("DC_NO_POSITIVE_EV")
        if edge is not None and edge<self.min_edge:blockers.append("DC_EDGE_BELOW_MINIMUM")
        adverse=self._num(stress.get("adverse_branch_probability"))
        if adverse is None:blockers.append("DC_ADVERSE_BRANCH_NOT_TESTED")
        elif adverse>=.20 and stress.get("adverse_branch_market") not in {"home_win","away_win","draw"}:blockers.append("DC_ADVERSE_BRANCH_INVALID")
        sensitivity=self._num(stress.get("probability_sensitivity"))
        if sensitivity is None:blockers.append("DC_SENSITIVITY_NOT_TESTED")
        elif sensitivity>.10:blockers.append("DC_REGIME_SENSITIVITY_HIGH")
        if stress.get("market_confirmed") is not True:warnings.append("DC_MARKET_CONFIRMATION_MISSING")
        return {"version":self.VERSION,"state":"BLOCK" if blockers else ("CAUTION" if warnings else "PASS"),"blockers":blockers,"warnings":warnings,"inputs":{"probability":p,"odds":odds,"edge":edge,"adverse_branch_probability":adverse,"probability_sensitivity":sensitivity,"market_confirmed":stress.get("market_confirmed")}}
