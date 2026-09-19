from __future__ import annotations
from .market_data import OddsSnapshot

class BasketballMarketAdapter:
    """Normalized boundary for bookmaker/odds providers.

    Provider-specific credentials and schemas stay outside the model core.
    No synthetic odds are generated here.
    """
    def normalize(self, fixture_id: str, source: str, payload: dict, captured_at: float) -> list[OddsSnapshot]:
        snapshots = []
        for quote in payload.get("quotes", []):
            try:
                snapshots.append(OddsSnapshot(
                    fixture_id=fixture_id,
                    market=str(quote["market"]),
                    selection=str(quote["selection"]),
                    odds=float(quote["odds"]),
                    captured_at=captured_at,
                    source=source,
                    is_closing=bool(quote.get("is_closing", False)),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return snapshots
