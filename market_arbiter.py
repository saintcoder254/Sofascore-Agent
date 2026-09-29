import re
import time

class MarketArbiter:
    """Football market-selection firewall."""
    VERSION="EMM-MARKET-ARBITER-v2.0"
    TOTALS={"TOTAL_GOALS","GOALS_OU","OVER_UNDER"}
    TEAM_TOTALS={"TEAM_GOALS","TEAM_TOTAL"}
    SUPPORTED={"1X2","BTTS","TOTAL_GOALS","DOUBLE_CHANCE","DNB","HANDICAP","CORNERS","CARDS","CORRECT_SCORE","TEAM_GOALS","TEAM_TOTAL"}

    def __init__(self,min_edge=0.05,min_ev=0.06,min_probability=0.60,min_sources=2,max_under_tail=0.22,max_over_lower_tail=0.35,min_history=8):
        self.min_edge=float(min_edge); self.min_ev=float(min_ev); self.min_probability=float(min_probability)
        self.min_sources=max(1,int(min_sources)); self.max_under_tail=float(max_under_tail)
        self.max_over_lower_tail=float(max_over_lower_tail); self.min_history=max(1,int(min_history))

    @staticmethod
    def _num(v):
        try:return float(v)
        except (TypeError,ValueError):return None

    @staticmethod
    def _market(v):
        s=re.sub(r"[^a-z0-9]+"," ",str(v or "").lower()).strip()
        if "btts" in s or "both teams" in s:return "BTTS"
        if "total goals" in s or "over under" in s or "goals o u" in s:return "TOTAL_GOALS"
        if "team total" in s or "team goals" in s:return "TEAM_GOALS"
        if "double chance" in s:return "DOUBLE_CHANCE"
        if "draw no bet" in s or s=="dnb":return "DNB"
        if "handicap" in s:return "HANDICAP"
        if "corner" in s:return "CORNERS"
        if "card" in s or "booking" in s:return "CARDS"
        if "correct score" in s:return "CORRECT_SCORE"
        if "winner" in s or s in {"1x2","match result"}:return "1X2"
        return s.upper()

    @staticmethod
    def _selection(v):return re.sub(r"\s+"," ",str(v or "").upper()).strip()

    @staticmethod
    def _implied(odds):
        o=MarketArbiter._num(odds); return None if o is None or o<=1 else 1.0/o

    @staticmethod
    def _line(selection):
        m=re.search(r"(?:OVER|UNDER|O|U)\s*([0-9]+(?:\.[05])?)",selection)
        return float(m.group(1)) if m else None

    @classmethod
    def _source_count(cls,evidence,market,selection):
        count=0
        for payload in (evidence.get("odds") or {}).values():
            if not isinstance(payload,dict):continue
            found=False
            for row in payload.get("markets",[]) or []:
                if cls._market(row.get("name") or row.get("marketName"))!=market:continue
                for choice in row.get("choices",[]) or []:
                    if cls._selection(choice.get("name") or choice.get("label"))==selection:found=True;break
                if found:break
            if found:count+=1
        ver=evidence.get("verification") or {}
        for key in ("sources","source_count","independent_sources"):
            n=cls._num(ver.get(key))
            if n is not None:count=max(count,int(n))
        return count

    def _tail(self,prediction,selection):
        line=self._line(self._selection(selection))
        if line is None:return {"available":False}
        totals=(prediction.get("probabilities") or {}).get("TOTAL_GOALS") or {}
        s=self._selection(selection)
        if s.startswith(("UNDER ","U")):
            risk=self._num(totals.get(f"OVER {line}"))
            return {"available":risk is not None,"risk":risk,"risk_type":"upper_tail","threshold":self.max_under_tail}
        if s.startswith(("OVER ","O")):
            risk=self._num(totals.get(f"UNDER {line}"))
            return {"available":risk is not None,"risk":risk,"risk_type":"lower_tail","threshold":self.max_over_lower_tail}
        return {"available":False}

    @staticmethod
    def _price_gate(odds,p):
        if odds is None or odds<=1 or p is None:return False,"INVALID_PRICE"
        if odds<1.20 and p<0.90:return False,"VERY_SHORT_PRICE_REQUIRES_P>=0.90"
        if odds<1.30 and p<0.85:return False,"SHORT_PRICE_REQUIRES_P>=0.85"
        return True,None

    def evaluate(self,prediction,evidence):
        sel=prediction.get("selection") or {}
        if not sel:return {"state":"BLOCK","version":self.VERSION,"reasons":["NO_SELECTION"],"generated_at":time.time()}
        market=self._market(sel.get("market")); selection=self._selection(sel.get("selection"))
        if market in {"TOTAL_POINTS","BASKETBALL_TOTAL","MONEYLINE_BASKETBALL"}:
            return {"state":"PASS","version":self.VERSION,"market":market,"selection":selection,"skipped":True,"reasons":[],"warnings":["NON_FOOTBALL_MARKET"],"generated_at":time.time()}
        odds=self._num(sel.get("odds")); p=self._num(sel.get("model_probability"))
        edge=self._num(sel.get("edge")); ev=self._num(sel.get("expected_value"))
        hist=prediction.get("history") or {}; sample=min(int(hist.get("home_games") or 0),int(hist.get("away_games") or 0))
        reasons=[]; warnings=[]; implied=self._implied(odds)
        if market not in self.SUPPORTED:reasons.append("UNSUPPORTED_MARKET")
        if p is None:reasons.append("MODEL_PROBABILITY_MISSING")
        if odds is None or odds<=1:reasons.append("INVALID_ODDS")
        if p is not None and p<self.min_probability:reasons.append("PROBABILITY_BELOW_GATE")
        if edge is not None and edge<self.min_edge:reasons.append("EDGE_BELOW_GATE")
        if ev is not None and ev<self.min_ev:reasons.append("EV_BELOW_GATE")
        if p is not None:
            ok,reason=self._price_gate(odds,p)
            if not ok:reasons.append(reason)
        sources=self._source_count(evidence,market,selection)
        if market in self.TOTALS|self.TEAM_TOTALS and sources<self.min_sources:reasons.append("INSUFFICIENT_INDEPENDENT_MARKET_SOURCES")
        if market in self.TOTALS|self.TEAM_TOTALS and sample<self.min_history:reasons.append("THIN_HISTORY_FOR_TOTALS")
        tail=self._tail(prediction,selection)
        if tail.get("available") and tail.get("risk") is not None:
            risk=float(tail["risk"])
            if tail["risk_type"]=="upper_tail" and risk>self.max_under_tail:reasons.append("UNDER_UPPER_TAIL_TOO_LARGE")
            if tail["risk_type"]=="lower_tail" and risk>self.max_over_lower_tail:reasons.append("OVER_LOWER_TAIL_TOO_LARGE")
        if p is not None and implied is not None and p-implied>0.20:reasons.append("UNEXPLAINED_MODEL_MARKET_DIVERGENCE")
        if p is not None and implied is not None and abs(p-implied)>0.12:warnings.append("LARGE_MODEL_MARKET_DIVERGENCE")
        if market=="TOTAL_GOALS" and not (prediction.get("probabilities") or {}).get("TOTAL_GOALS"):reasons.append("TOTAL_MODEL_MISSING")
        return {"state":"PASS" if not reasons else "BLOCK","version":self.VERSION,"market":market,"selection":selection,"odds":odds,"model_probability":p,"market_implied_probability":implied,"edge":edge,"expected_value":ev,"sample":sample,"independent_market_sources":sources,"tail_risk":tail,"reasons":reasons,"warnings":warnings,"generated_at":time.time()}
