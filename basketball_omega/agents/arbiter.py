from basketball_omega.contracts import AgentOpinion, FusionVerdict

class BasketballFinalArbiter:
    name="basketball-final-arbiter"
    def decide(self,opinions,market=None,max_disagreement=.12,min_edge=.025):
        margins=[o.fair_margin for o in opinions if o.fair_margin is not None]; totals=[o.fair_total for o in opinions if o.fair_total is not None]
        if not margins:return FusionVerdict("NO_BET",0,None,None,None,[],[],["No independent fair-margin estimate."],opinions)
        fair_margin=sum(margins)/len(margins); fair_total=sum(totals)/len(totals) if totals else None
        disagreement=(max(margins)-min(margins))/max(10,abs(fair_margin)) if margins else 1
        blocked=[]
        if disagreement>max_disagreement:blocked.append("model_disagreement")
        if any(o.verdict=="CHALLENGE_RAISED" for o in opinions):blocked.append("adversarial_challenge")
        rec=[]
        if market:
            if market.get("spread") is not None:
                edge=fair_margin+float(market["spread"])
                if abs(edge)>=min_edge*100:rec.append({"market":"spread","fair_value":fair_margin,"line":market["spread"],"edge_points":edge})
            if market.get("total") is not None and fair_total is not None:
                edge=fair_total-float(market["total"])
                if abs(edge)>=min_edge*100:rec.append({"market":"total","fair_value":fair_total,"line":market["total"],"edge_points":edge})
        state="NO_BET" if blocked or not rec else "QUALIFIED_CANDIDATE"
        confidence=max(.2,min(.95,sum(o.confidence for o in opinions)/len(opinions)))
        return FusionVerdict(state,confidence,fair_margin,fair_total,None,rec,[],blocked,opinions,{"margin_disagreement":disagreement})
