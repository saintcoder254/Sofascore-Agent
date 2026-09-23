import hashlib
import json
import time
import datetime
import logging
from curl_cffi.requests import AsyncSession

logger = logging.getLogger("emm.sofascore")

class SofaScoreAdapter:
    def __init__(self, base_url, timeout=15):
        self.base_url=base_url.rstrip("/")
        self.timeout=timeout
        self.client=AsyncSession(impersonate="chrome",timeout=timeout,headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            "Accept":"application/json, text/plain, */*","Accept-Language":"en-US,en;q=0.9",
            "Referer":"https://www.sofascore.com/","Origin":"https://www.sofascore.com",
            "X-Requested-With":"XMLHttpRequest","Sec-Fetch-Dest":"empty","Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"same-origin"})
        self.metrics={"requests_total":0,"requests_success":0,"requests_failed":0,"last_request_at":None,"last_success_at":None,"last_error_at":None,"last_status_code":None,"last_path":None,"last_latency_ms":None}
    async def close(self): await self.client.close()
    async def get_json(self,path):
        started=time.perf_counter(); self.metrics["requests_total"]+=1; self.metrics["last_request_at"]=time.time(); self.metrics["last_path"]=path
        try:
            r=await self.client.get(f"{self.base_url}/{path.lstrip('/')}")
            self.metrics["last_latency_ms"]=round((time.perf_counter()-started)*1000,1); self.metrics["last_status_code"]=r.status_code
            r.raise_for_status(); payload=r.json(); self.metrics["requests_success"]+=1; self.metrics["last_success_at"]=time.time(); return payload
        except Exception as exc:
            self.metrics["last_latency_ms"]=round((time.perf_counter()-started)*1000,1); self.metrics["requests_failed"]+=1; self.metrics["last_error_at"]=time.time(); logger.error("SOFASCORE_HTTP_ERROR path=%s error=%r",path,exc); raise
    async def today_events(self):
        d=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        return await self.get_json(f"/sport/football/scheduled-events/{d}")
    async def event(self,event_id): return await self.get_json(f"/event/{event_id}")
    async def event_statistics(self,event_id): return await self.get_json(f"/event/{event_id}/statistics")
    async def event_shotmap(self,event_id): return await self.get_json(f"/event/{event_id}/shotmap")
    async def event_incidents(self,event_id): return await self.get_json(f"/event/{event_id}/incidents")
    async def event_lineups(self,event_id): return await self.get_json(f"/event/{event_id}/lineups")
    async def team_last_events(self,team_id,page=0): return await self.get_json(f"/team/{team_id}/events/last/{int(page)}")
    async def team_next_events(self,team_id,page=0): return await self.get_json(f"/team/{team_id}/events/next/{int(page)}")
    async def event_h2h(self,event_id): return await self.get_json(f"/event/{event_id}/h2h/events")
    @staticmethod
    def payload_hash(payload): return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    @staticmethod
    def now(): return time.time()
