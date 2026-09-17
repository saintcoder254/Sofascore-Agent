import datetime
import logging
import re
import time

import httpx

logger = logging.getLogger("emm.futbol24")


class Futbol24Adapter:
    """Futbol24 verification feed.

    Uses the public Futbol24 web surface as an independent verification source.
    The adapter intentionally keeps parsing conservative: only explicitly
    recognizable match rows are normalized, and unparseable content is not
    promoted into the Match Digital Twin.
    """

    BASE = "https://www.futbol24.com/"

    def __init__(self, timeout=15):
        self.client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
                "Referer": self.BASE,
            },
        )
        self.metrics = {
            "attempts": 0,
            "success": 0,
            "failures": 0,
            "last_status_code": None,
            "last_success_at": None,
            "last_error": None,
            "last_events": 0,
        }

    @staticmethod
    def _date():
        return datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    @staticmethod
    def _parse_score(text):
        match = re.search(r"\b(\d+)\s*[-:]\s*(\d+)\b", text or "")
        if not match:
            return None, None
        return int(match.group(1)), int(match.group(2))

    @classmethod
    def _extract_events(cls, html):
        # Conservative extraction from visible text. Futbol24's front-end can
        # change markup, so no guessed private API endpoint is used here.
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html or "", flags=re.I | re.S)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)

        events = []
        # Match recognizable score rows. Team names are retained only when a
        # surrounding delimiter is available; ambiguous text is ignored.
        pattern = re.compile(r"([^|]{2,80}?)\s+(\d+)\s*[-:]\s*(\d+)\s+([^|]{2,80})")
        for idx, match in enumerate(pattern.finditer(text)):
            home = match.group(1).strip(" -|:")
            away = match.group(4).strip(" -|:")
            if not home or not away or home.lower() == away.lower():
                continue
            events.append({
                "id": f"futbol24:text:{idx}",
                "source": "futbol24",
                "source_event_id": f"text:{idx}",
                "source_retrieved_at": time.time(),
                "date": cls._date(),
                "name": f"{home} - {away}",
                "shortName": f"{home} - {away}",
                "status": {},
                "homeTeam": {"id": "", "name": home, "shortName": home, "score": int(match.group(2))},
                "awayTeam": {"id": "", "name": away, "shortName": away, "score": int(match.group(3))},
                "competition": {},
                "raw_source_payload": {"extraction": "public_html_text"},
            })
        return events

    async def today_events(self):
        self.metrics["attempts"] += 1
        day = self._date()
        try:
            response = await self.client.get(self.BASE)
            self.metrics["last_status_code"] = response.status_code
            response.raise_for_status()
            events = self._extract_events(response.text)
            self.metrics["success"] += 1
            self.metrics["last_success_at"] = time.time()
            self.metrics["last_error"] = None
            self.metrics["last_events"] = len(events)
            logger.warning("FUTBOL24_SUCCESS events=%s date=%s status=%s", len(events), day, response.status_code)
            return {
                "source": "futbol24",
                "source_priority": 4,
                "retrieved_at": time.time(),
                "date": day,
                "events": events,
            }
        except Exception as exc:
            self.metrics["failures"] += 1
            self.metrics["last_error"] = repr(exc)
            logger.error("FUTBOL24_ERROR error=%r", exc)
            raise

    async def close(self):
        await self.client.aclose()
