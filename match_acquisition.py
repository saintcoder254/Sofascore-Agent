import asyncio, time

class MatchAcquisitionEngine:
    """Build a normalized evidence bundle for a fixture before UMIOS analysis."""
    def __init__(self, fusion):
        self.fusion = fusion

    async def enrich_event(self, event_id):
        p = self.fusion.primary
        tasks = {
            "event": p.event(event_id),
            "statistics": p.event_statistics(event_id),
            "shotmap": p.event_shotmap(event_id),
            "incidents": p.event_incidents(event_id),
            "lineups": p.event_lineups(event_id),
        }
        results = {}
        for key, task in tasks.items():
            try:
                results[key] = await task
            except Exception as exc:
                results[key] = {"error": repr(exc)}
        odds = {}
        for path in (f"/event/{event_id}/odds/1", f"/event/{event_id}/odds/2"):
            try:
                data = await p.get_json(path)
                odds[path.rsplit("/", 1)[-1]] = data
            except Exception as exc:
                odds[path.rsplit("/", 1)[-1]] = {"error": repr(exc)}
        results["odds"] = odds
        results["retrieved_at"] = time.time()
        return results

    async def acquire(self, event_id):
        base = self.fusion.primary
        bundle = await self.enrich_event(event_id)
        verification = {}
        try:
            verification = await self.fusion.verify_futbol24()
        except Exception as exc:
            verification = {"error": repr(exc)}
        bundle["verification"] = verification
        return bundle
