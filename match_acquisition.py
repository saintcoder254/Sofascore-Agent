import asyncio, time

class MatchAcquisitionEngine:
    """Build the complete evidence bundle used by the UMIOS probability engine."""
    def __init__(self,fusion): self.fusion=fusion

    async def enrich_event(self,event_id):
        p=self.fusion.primary
        base={}
        tasks={
            "event":p.event(event_id),"statistics":p.event_statistics(event_id),
            "shotmap":p.event_shotmap(event_id),"incidents":p.event_incidents(event_id),
            "lineups":p.event_lineups(event_id),"h2h":p.event_h2h(event_id),
        }
        for key,task in tasks.items():
            try: base[key]=await task
            except Exception as exc: base[key]={"error":repr(exc)}
        event=base.get("event") or {}
        teams=[event.get("homeTeam") or {},event.get("awayTeam") or {}]
        history={}
        for side,team in zip(("home","away"),teams):
            tid=team.get("id")
            if not tid: history[side]={"events":[],"error":"missing_team_id"}; continue
            try:
                pages=[]
                for page in (0,1):
                    try: pages.append(await p.team_last_events(tid,page))
                    except Exception as exc: pages.append({"events":[],"error":repr(exc)})
                history[side]={"events":[e for x in pages for e in (x.get("events") or [])][:20]}
            except Exception as exc: history[side]={"events":[],"error":repr(exc)}
        base["history"]=history
        odds={}
        for path in (f"/event/{event_id}/odds/1",f"/event/{event_id}/odds/2"):
            try: odds[path.rsplit("/",1)[-1]]=await p.get_json(path)
            except Exception as exc: odds[path.rsplit("/",1)[-1]]={"error":repr(exc)}
        base["odds"]=odds;base["retrieved_at"]=time.time()
        return base

    async def acquire(self,event_id):
        bundle=await self.enrich_event(event_id)
        try: bundle["verification"]=await self.fusion.verify_futbol24()
        except Exception as exc: bundle["verification"]={"error":repr(exc)}
        return bundle
