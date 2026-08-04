"""Polygon.io market data adapter (requires POLYGON_API_KEY)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

import httpx

from ai_trading_shared.domain.enums import AssetClass
from ai_trading_shared.utils.logging import get_logger
from market_data.domain.models import OHLCVBar, Quote

logger = get_logger(__name__)


class PolygonMarketDataProvider:
    """Fetches daily aggregates from Polygon when licensed credentials exist."""

    name = "polygon"

    def __init__(self, api_key: str, base_url: str = "https://api.polygon.io") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def fetch_ohlcv(
        self,
        ticker: str,
        *,
        lookback_days: int = 60,
        asset_class: AssetClass = AssetClass.STOCK,
    ) -> List[OHLCVBar]:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=lookback_days + 10)
        url = (
            f"{self._base_url}/v2/aggs/ticker/{ticker.upper()}/range/1/day/"
            f"{start.isoformat()}/{end.isoformat()}"
        )
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": self._api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        bars: List[OHLCVBar] = []
        for row in data.get("results", []):
            ts = datetime.fromtimestamp(row["t"] / 1000.0, tz=timezone.utc)
            bars.append(
                OHLCVBar(
                    ticker=ticker.upper(),
                    asset_class=asset_class,
                    timestamp=ts,
                    open=Decimal(str(row["o"])),
                    high=Decimal(str(row["h"])),
                    low=Decimal(str(row["l"])),
                    close=Decimal(str(row["c"])),
                    volume=Decimal(str(row.get("v", 0))),
                    vwap=Decimal(str(row["vw"])) if row.get("vw") is not None else None,
                )
            )
        logger.info("polygon_bars_fetched", ticker=ticker, count=len(bars))
        return bars[-lookback_days:]

    async def fetch_quote(self, ticker: str) -> Quote:
        url = f"{self._base_url}/v2/last/nbbo/{ticker.upper()}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, params={"apiKey": self._api_key})
            response.raise_for_status()
            payload = response.json().get("results", {})
        bid = Decimal(str(payload.get("P") or payload.get("bid_price") or 0))
        ask = Decimal(str(payload.get("p") or payload.get("ask_price") or 0))
        last = ask if ask > 0 else bid
        return Quote(
            ticker=ticker.upper(),
            bid=bid,
            ask=ask,
            bid_size=Decimal(str(payload.get("S") or 0)),
            ask_size=Decimal(str(payload.get("s") or 0)),
            last=last,
            timestamp=datetime.now(timezone.utc),
        )
