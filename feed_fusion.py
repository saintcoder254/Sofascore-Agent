import datetime
import logging
import time
import httpx
from sofascore_adapter import SofaScoreAdapter
from fotmob_adapter import FotMobAdapter
from futbol24_adapter import Futbol24Adapter
from scores24_adapter import Scores24Adapter

logger = logging.getLogger("emm.fusion")

class FeedFusionAdapter:
    """Multi-source football acquisition with independent final-result witnesses."""
    ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"

    def __init__(self, sofascore_base, timeout=15):
        self.primary=SofaScoreAdapter(sofascore_base,timeout)
        self.fotmob=FotMobAdapter(timeout)
        self.futbol24=Futbol24Adapter(timeout)
        self.scores24=Scores24Adapter(timeout)
        self.timeout=timeout
        self.fallback_client=httpx.AsyncClient(timeout=timeout,headers={"Accept":"application/json","User-Agent":"EliteMatchMaster/1.0 feed-fusion"})
        self.active_source=None
        self.metrics={"primary_attempts":0,"primary_success":0,"primary_failures":0,"espn_attempts":0,"espn_success":0,"espn_failures":0,"fotmob_attempts":0,"fotmob_success":0,"fotmob_failures":0,"futbol24_attempts":0,"futbol24_success":0,"futbol24_failures":0,"futbol24_verification_events":0,"futbol24_score_conflicts":0,"last_futbol24_at":None,"scores24_attempts":0,"scores24_success":0,"scores24_failures":0,"scores24_observations":0,"last_scores24_at":None,"final_verification_attempts":0,"final_verification_sources":0,"final_verification_events":0,"last_final_verification_at":None,"last_source":None,"last_error":None,"last_success_at":None}

    @property
    def primary_metrics(self): return self.primary.metrics
    @staticmethod
    def _date(): return datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    @staticmethod
    def _normalize_espn(payload):
        events=[]
        for event in payload.get("events",[]):
            competitions=event.get("competitions") or []
            competition=competitions[0] if competitions else {}
            competitors=competition.get("competitors") or []
            home=next((c for c in competitors if c.get("homeAway")=="home"),{})
            away=next((c for c in competitors if c.get("homeAway")=="away"),{})
            status=(event.get("status") or {}).get("type") or {}
            events.append({"id":str(event.get("id","")),"source":"espn","source_event_id":str(event.get("id","")),"source_retrieved_at":time.time(),"date":event.get("date"),"name":event.get("name"),"shortName":event.get("shortName"),"status":status,"homeTeam":{"id":str((home.get("team") or {}).get("id","")),"name":(home.get("team") or {}).get("displayName"),"shortName":(home.get("team") or {}).get("shortDisplayName"),"score":home.get("score")},"awayTeam":{"id":str((away.get("team") or {}).get("id","")),"name":(away.get("team") or {}).get("displayName"),"shortName":(away.get("team") or {}).get("shortDisplayName"),"score":away.get("score")},"competition":competition.get("league") or {},"raw_source_payload":event})
        return {"source":"espn","source_priority":2,"retrieved_at":time.time(),"date":payload.get("day",{}).get("date") or FeedFusionAdapter._date(),"events":events}
    async def _fallback_espn(self):
        self.metrics["espn_attempts"]+=1; day=self._date().replace("-","")
        try:
            r=await self.fallback_client.get(self.ESPN_BASE,params={"dates":day}); r.raise_for_status(); p=self._normalize_espn(r.json())
            if not p["events"]: raise RuntimeError("ESPN returned no match events")
            self.metrics["espn_success"]+=1; self.metrics["last_source"]="espn"; self.metrics["last_success_at"]=time.time(); self.active_source="espn"; return p
        except Exception as exc: self.metrics["espn_failures"]+=1; self.metrics["last_error"]=repr(exc); raise
    async def _fallback_fotmob(self):
        self.metrics["fotmob_attempts"]+=1
        try:
            p=await self.fotmob.today_events(); self.metrics["fotmob_success"]+=1; self.metrics["last_source"]="fotmob"; self.metrics["last_success_at"]=time.time(); self.active_source="fotmob"; return p
        except Exception as exc: self.metrics["fotmob_failures"]+=1; self.metrics["last_error"]=repr(exc); raise
    async def verify_futbol24(self):
        self.metrics["futbol24_attempts"]+=1
        try:
            p=await self.futbol24.today_events(); self.metrics["futbol24_success"]+=1; self.metrics["futbol24_verification_events"]=len(p.get("events",[])); self.metrics["last_futbol24_at"]=time.time(); return p
        except Exception as exc: self.metrics["futbol24_failures"]+=1; return {"source":"futbol24","events":[],"error":repr(exc),"retrieved_at":time.time()}
    async def query_scores24(self):
        self.metrics["scores24_attempts"]+=1
        try: p=await self.scores24.today_predictions()
        except Exception as exc: self.metrics["scores24_failures"]+=1; return {"source":"scores24","observations":[],"error":repr(exc),"retrieved_at":time.time()}
        n=len(p.get("observations",[])); self.metrics["scores24_observations"]=n
        if n: self.metrics["scores24_success"]+=1; self.metrics["last_scores24_at"]=time.time()
        else: self.metrics["scores24_failures"]+=1
        return p
    async def verify_final_results(self, futbol24_payload=None):
        """Fetch final-score witnesses independently of the active primary feed."""
        self.metrics["final_verification_attempts"]+=1
        witnesses=[]
        try:
            p=await self._fallback_espn(); witnesses.append(p)
        except Exception: pass
        try:
            p=await self._fallback_fotmob(); witnesses.append(p)
        except Exception: pass
        if futbol24_payload is None: futbol24_payload=await self.verify_futbol24()
        if futbol24_payload and futbol24_payload.get("events"):
            # Futbol24 parser returns explicit scores but not a typed completion state.
            fp=dict(futbol24_payload); fp["events"]=[]
            for e in futbol24_payload.get("events",[]):
                e=dict(e); e["status"]={"type":{"state":"finished","completed":True}}; fp["events"].append(e)
            witnesses.append(fp)
        self.metrics["final_verification_sources"]=len(witnesses)
        self.metrics["final_verification_events"]=sum(len(x.get("events",[])) for x in witnesses)
        self.metrics["last_final_verification_at"]=time.time()
        return {"sources":witnesses,"required_independent_sources":2,"retrieved_at":time.time()}
    @staticmethod
    def _team_key(team): return str((team or {}).get("name") or "").strip().lower()
    def reconcile_scores(self, active_payload, verification_payload):
        conflicts=[]
        for ve in verification_payload.get("events",[]) if verification_payload else []:
            vh,va=ve.get("homeTeam") or {},ve.get("awayTeam") or {}
            if vh.get("score") is None or va.get("score") is None: continue
            for ae in active_payload.get("events",[]) if active_payload else []:
                ah,aa=ae.get("homeTeam") or {},ae.get("awayTeam") or {}
                if self._team_key(vh)==self._team_key(ah) and self._team_key(va)==self._team_key(aa) and (str(vh.get("score")),str(va.get("score")))!=(str(ah.get("score")),str(aa.get("score"))):
                    conflicts.append({"active_id":ae.get("id"),"verification_id":ve.get("id"),"active_score":[ah.get("score"),aa.get("score")],"verification_score":[vh.get("score"),va.get("score")]})
        self.metrics["futbol24_score_conflicts"]+=len(conflicts); return conflicts
    async def today_events(self):
        self.metrics["primary_attempts"]+=1
        try:
            payload=await self.primary.today_events(); payload["source"]="sofascore"; payload["source_priority"]=1; payload["retrieved_at"]=time.time(); self.metrics["primary_success"]+=1; self.metrics["last_source"]="sofascore"; self.metrics["last_success_at"]=time.time(); self.active_source="sofascore"
        except Exception as primary_exc:
            self.metrics["primary_failures"]+=1; self.metrics["last_error"]=repr(primary_exc)
            try: payload=await self._fallback_espn()
            except Exception:
                try: payload=await self._fallback_fotmob()
                except Exception as exc: raise RuntimeError("All football acquisition sources failed") from exc
        verification=await self.verify_futbol24()
        scores24=await self.query_scores24()
        final_verification=await self.verify_final_results(verification)
        payload["verification"]={"futbol24":verification,"scores24":scores24,"final_results":final_verification}
        payload["verification_conflicts"]=self.reconcile_scores(payload,verification)
        return payload
    def payload_hash(self,payload): return self.primary.payload_hash(payload)
    async def close(self): await self.primary.close(); await self.fotmob.close(); await self.futbol24.close(); await self.scores24.close(); await self.fallback_client.aclose()
