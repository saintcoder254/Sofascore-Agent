import hashlib, json, time, datetime
import httpx

class SofaScoreAdapter:
    def __init__(self, base_url, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "EliteMatchMaster-SofaScore-Agent/1.0"}
        )

    async def close(self):
        await self.client.aclose()

    async def get_json(self, path):
        r = await self.client.get(f"{self.base_url}/{path.lstrip('/')}")
        r.raise_for_status()
        return r.json()

    async def today_events(self):
        d = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        return await self.get_json(f"/sport/football/scheduled-events/{d}")

    async def event(self, event_id):
        return await self.get_json(f"/event/{event_id}")

    async def event_statistics(self, event_id):
        return await self.get_json(f"/event/{event_id}/statistics")

    async def event_shotmap(self, event_id):
        return await self.get_json(f"/event/{event_id}/shotmap")

    async def event_incidents(self, event_id):
        return await self.get_json(f"/event/{event_id}/incidents")

    async def event_lineups(self, event_id):
        return await self.get_json(f"/event/{event_id}/lineups")

    @staticmethod
    def payload_hash(payload):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def now():
        return time.time()
