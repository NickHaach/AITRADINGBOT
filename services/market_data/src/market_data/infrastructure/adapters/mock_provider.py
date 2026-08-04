"""Deterministic synthetic OHLCV generator for offline development."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List

import numpy as np

from ai_trading_shared.domain.enums import AssetClass
from market_data.domain.models import OHLCVBar, Quote


# Seed prices / drift / vol for a small liquid universe
_SPECS: Dict[str, Dict[str, float]] = {
    "AAPL": {"px": 190.0, "mu": 0.0004, "sigma": 0.012},
    "MSFT": {"px": 420.0, "mu": 0.0003, "sigma": 0.011},
    "NVDA": {"px": 120.0, "mu": 0.0010, "sigma": 0.025},
    "SPY": {"px": 520.0, "mu": 0.0002, "sigma": 0.008},
    "QQQ": {"px": 450.0, "mu": 0.0003, "sigma": 0.010},
    "XOM": {"px": 110.0, "mu": 0.0001, "sigma": 0.014},
    "JPM": {"px": 195.0, "mu": 0.0002, "sigma": 0.013},
    "TSLA": {"px": 250.0, "mu": 0.0005, "sigma": 0.030},
    "BTC-USD": {"px": 65000.0, "mu": 0.0008, "sigma": 0.035},
}


class MockMarketDataProvider:
    """GBM-style bar generator with stable seeds per ticker."""

    name = "mock"

    async def fetch_ohlcv(
        self,
        ticker: str,
        *,
        lookback_days: int = 60,
        asset_class: AssetClass = AssetClass.STOCK,
    ) -> List[OHLCVBar]:
        spec = _SPECS.get(ticker.upper(), {"px": 100.0, "mu": 0.0002, "sigma": 0.015})
        seed = abs(hash(ticker.upper())) % (2**32)
        rng = np.random.default_rng(seed)
        n = max(lookback_days, 5)
        now = datetime.now(timezone.utc).replace(hour=21, minute=0, second=0, microsecond=0)

        price = spec["px"]
        bars: List[OHLCVBar] = []
        for i in range(n, 0, -1):
            shock = rng.normal(spec["mu"], spec["sigma"])
            open_px = price
            close_px = max(0.01, open_px * float(np.exp(shock)))
            high_px = max(open_px, close_px) * float(1.0 + abs(rng.normal(0, 0.003)))
            low_px = min(open_px, close_px) * float(1.0 - abs(rng.normal(0, 0.003)))
            volume = Decimal(str(round(float(rng.uniform(1.0e6, 8.0e6)), 2)))
            ts = now - timedelta(days=i)
            bars.append(
                OHLCVBar(
                    ticker=ticker.upper(),
                    asset_class=asset_class if ticker.upper() != "BTC-USD" else AssetClass.CRYPTO,
                    timestamp=ts,
                    open=Decimal(str(round(open_px, 4))),
                    high=Decimal(str(round(high_px, 4))),
                    low=Decimal(str(round(low_px, 4))),
                    close=Decimal(str(round(close_px, 4))),
                    volume=volume,
                    vwap=Decimal(str(round((open_px + close_px) / 2.0, 4))),
                )
            )
            price = close_px
        return bars

    async def fetch_quote(self, ticker: str) -> Quote:
        bars = await self.fetch_ohlcv(ticker, lookback_days=5)
        last = bars[-1].close
        spread = last * Decimal("0.0005")
        return Quote(
            ticker=ticker.upper(),
            bid=last - spread / 2,
            ask=last + spread / 2,
            bid_size=Decimal("100"),
            ask_size=Decimal("100"),
            last=last,
            timestamp=datetime.now(timezone.utc),
        )
