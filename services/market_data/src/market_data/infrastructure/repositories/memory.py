"""In-memory market data repository."""

from __future__ import annotations

from typing import Dict, List, Optional

from market_data.domain.models import MarketFeatures, OHLCVBar


class InMemoryMarketRepository:
    def __init__(self) -> None:
        self._bars: Dict[str, List[OHLCVBar]] = {}
        self._features: Dict[str, MarketFeatures] = {}

    async def upsert_bars(self, bars: List[OHLCVBar]) -> int:
        if not bars:
            return 0
        ticker = bars[0].ticker.upper()
        existing = {b.timestamp.isoformat(): b for b in self._bars.get(ticker, [])}
        for bar in bars:
            existing[bar.timestamp.isoformat()] = bar
        merged = sorted(existing.values(), key=lambda b: b.timestamp)
        self._bars[ticker] = merged
        return len(bars)

    async def get_bars(self, ticker: str, limit: int = 60) -> List[OHLCVBar]:
        bars = self._bars.get(ticker.upper(), [])
        return bars[-limit:]

    async def save_features(self, features: MarketFeatures) -> MarketFeatures:
        self._features[features.ticker.upper()] = features
        return features

    async def get_features(self, ticker: str) -> Optional[MarketFeatures]:
        return self._features.get(ticker.upper())

    async def list_tickers(self) -> List[str]:
        return sorted(set(self._bars.keys()) | set(self._features.keys()))
