import hashlib
import json
import time
import datetime
import logging

from curl_cffi.requests import AsyncSession

logger = logging.getLogger("emm.sofascore")


class SofaScoreAdapter:
    def __init__(self, base_url, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.client = AsyncSession(
            impersonate="chrome",
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.sofascore.com/",
                "Origin": "https://www.sofascore.com",
            },
        )

        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "last_request_at": None,
            "last_success_at": None,
            "last_error_at": None,
            "last_status_code": None,
            "last_path": None,
            "last_latency_ms": None,
        }

    async def close(self):
        # curl_cffi AsyncSession uses close(), not aclose()
        self.client.close()

    async def get_json(self, path):
        started = time.perf_counter()

        self.metrics["requests_total"] += 1
        self.metrics["last_request_at"] = time.time()
        self.metrics["last_path"] = path

        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            r = await self.client.get(url)

            latency = round(
                (time.perf_counter() - started) * 1000,
                1,
            )

            self.metrics["last_latency_ms"] = latency
            self.metrics["last_status_code"] = r.status_code

            r.raise_for_status()

            payload = r.json()

            self.metrics["requests_success"] += 1
            self.metrics["last_success_at"] = time.time()

            logger.info(
                "SOFASCORE_HTTP status=%s path=%s latency_ms=%s",
                r.status_code,
                path,
                latency,
            )

            return payload

        except Exception as exc:
            latency = round(
                (time.perf_counter() - started) * 1000,
                1,
            )

            self.metrics["last_latency_ms"] = latency
            self.metrics["requests_failed"] += 1
            self.metrics["last_error_at"] = time.time()

            logger.error(
                "SOFASCORE_HTTP_ERROR path=%s latency_ms=%s error=%r",
                path,
                latency,
                exc,
            )

            raise

    async def today_events(self):
        d = datetime.datetime.now(
            datetime.timezone.utc
        ).date().isoformat()

        return await self.get_json(
            f"/sport/football/scheduled-events/{d}"
        )

    async def event(self, event_id):
        return await self.get_json(
            f"/event/{event_id}"
        )

    async def event_statistics(self, event_id):
        return await self.get_json(
            f"/event/{event_id}/statistics"
        )

    async def event_shotmap(self, event_id):
        return await self.get_json(
            f"/event/{event_id}/shotmap"
        )

    async def event_incidents(self, event_id):
        return await self.get_json(
            f"/event/{event_id}/incidents"
        )

    async def event_lineups(self, event_id):
        return await self.get_json(
            f"/event/{event_id}/lineups"
        )

    @staticmethod
    def payload_hash(payload):
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def now():
        return time.time()
