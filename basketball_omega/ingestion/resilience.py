"""Transport-level resilience: retries, exponential backoff, rate limiting."""
import time, random
class ResilientFetcher:
    def __init__(self, fetch, retries=4, base_delay=0.5, max_delay=8.0, sleep=time.sleep):
        self.fetch=fetch; self.retries=max(1,int(retries)); self.base_delay=float(base_delay); self.max_delay=float(max_delay); self.sleep=sleep
    def get(self, url, **kwargs):
        last=None
        for attempt in range(self.retries):
            try:
                value=self.fetch(url,**kwargs)
                if value is None: raise ValueError("empty_response")
                return value
            except Exception as exc:
                last=exc
                if attempt+1==self.retries: break
                delay=min(self.max_delay,self.base_delay*(2**attempt))+random.random()*0.1
                self.sleep(delay)
        raise RuntimeError(f"source_fetch_failed:{url}") from last
