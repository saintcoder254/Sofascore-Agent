import logging
import re
import time
from html import unescape
import httpx

logger = logging.getLogger("emm.scores24")

class Scores24Adapter:
    """External prediction intelligence feed; never a primary match feed."""
    URL = "https://scores24.live/en/predictions/soccer/today"
    SOURCE = "scores24"
    METHODOLOGY = {
        "published_method": "Scores24 describes forecasts using form, scoring and defensive statistics, home/away performance, H2H, lineups/injuries, standings/motivation, coaching context, weather and expert analysis.",
        "model_transparency": "partial",
        "independent_model_details": "not fully disclosed publicly",
        "markets_observed": ["1X2", "Over/Under", "BTTS", "Double Chance", "Handicap", "Correct Score"],
        "role_in_umios": "external_forecaster / challenger",
    }

    def __init__(self, timeout=15):
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0 Safari/537.36",
        })
        self.metrics = {"attempts": 0, "success": 0, "failures": 0, "last_success_at": None, "last_error": None, "last_items": 0}

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", unescape(value or "")).strip()

    @classmethod
    def _extract_prediction_cards(cls, html):
        text = cls._clean(re.sub(r"<[^>]+>", " ", html))
        pattern = re.compile(r"(?P<home>[A-Za-zÀ-ÿ0-9.'’&()\- ]{2,70})\s+(?P<away>[A-Za-zÀ-ÿ0-9.'’&()\- ]{2,70})\s+(?P<time>\d{1,2}:\d{2})\s+(?P<pred>(?:Total goals|Both Teams To Score|Match Winner|Double Chance|Handicap)[^0-9]{0,30}(?:\([^)]*\)|Yes|No|1X|X2|12|1|X|2))")
        out, seen = [], set()
        for m in pattern.finditer(text):
            home, away, pred = cls._clean(m.group("home")), cls._clean(m.group("away")), cls._clean(m.group("pred"))
            if len(home.split()) > 8 or len(away.split()) > 8: continue
            key = (home.lower(), away.lower(), pred.lower())
            if key not in seen:
                seen.add(key); out.append({"home": home, "away": away, "kickoff_local": m.group("time"), "prediction": pred})
        return out[:500]

    async def today_predictions(self):
        self.metrics["attempts"] += 1
        retrieved_at = time.time()
        try:
            response = await self.client.get(self.URL)
            response.raise_for_status()
            observations = self._extract_prediction_cards(response.text)
            self.metrics.update({"success": self.metrics["success"] + 1, "last_success_at": time.time(), "last_error": None, "last_items": len(observations)})
            logger.info("SCORES24_FETCH_SUCCESS observations=%s", len(observations))
            return {"source": self.SOURCE, "source_priority": 5, "retrieved_at": retrieved_at, "url": self.URL, "methodology": self.METHODOLOGY, "observations": observations, "http_status": response.status_code}
        except Exception as exc:
            self.metrics["failures"] += 1; self.metrics["last_error"] = repr(exc)
            logger.warning("SCORES24_FETCH_FAILED error=%r", exc)
            return {"source": self.SOURCE, "source_priority": 5, "retrieved_at": retrieved_at, "url": self.URL, "methodology": self.METHODOLOGY, "observations": [], "error": repr(exc)}

    async def close(self):
        await self.client.aclose()
