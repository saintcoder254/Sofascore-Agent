import json,time,random
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

class HTTPJSONTransport:
    """Rate-limited, retrying transport for public JSON endpoints."""
    def __init__(self,timeout=30,rate_per_second=.5,max_retries=5,user_agent="Basketball-OMEGA/1.0"):
        self.timeout=timeout; self.interval=1/max(rate_per_second,1e-3); self.max_retries=max_retries
        self.user_agent=user_agent; self._last=0.0
    def get(self,url):
        last=None
        for attempt in range(self.max_retries):
            wait=self.interval-(time.time()-self._last)
            if wait>0: time.sleep(wait)
            try:
                req=Request(url,headers={"User-Agent":self.user_agent,"Accept":"application/json"})
                with urlopen(req,timeout=self.timeout) as r:
                    raw=r.read()
                self._last=time.time()
                if not raw: raise ValueError("empty_response")
                return json.loads(raw)
            except (HTTPError,URLError,TimeoutError,ValueError) as exc:
                last=exc
                time.sleep(min(30,(2**attempt)*.5+random.random()*.25))
        raise RuntimeError(f"transport_failed:{url}:{last}")
