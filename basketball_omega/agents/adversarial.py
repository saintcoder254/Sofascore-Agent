from basketball_omega.contracts import BasketballContext, AgentOpinion

class AdversarialAgent:
    name="adversarial-truth"
    def run(self,ctx,opinions)->AgentOpinion:
        margins=[o.fair_margin for o in opinions if o.fair_margin is not None]; risks=[]
        disagreement=max(margins)-min(margins) if margins else 999
        if disagreement>10: risks.append("Agent fair-margin disagreement exceeds 10 points.")
        questionable=sum(1 for x in ctx.injuries.values() if str(x.get("status","")).lower() in {"questionable","gtd","game-time"})
        if questionable: risks.append("Availability uncertainty can dominate model edge.")
        if len(ctx.history)<10: risks.append("Thin historical sample.")
        return AgentOpinion(self.name,"CHALLENGE_PASS" if not risks else "CHALLENGE_RAISED",max(.2,1-min(1,disagreement/20)),risks=risks,evidence={"margin_disagreement":disagreement,"questionable_players":questionable})
