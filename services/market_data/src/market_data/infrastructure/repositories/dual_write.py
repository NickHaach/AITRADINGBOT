"""Dual-write market repository: memory for speed, optional SQL persistence."""

from __future__ import annotations

from typing import List, Optional

from ai_trading_shared.infrastructure.repositories.persistence import MarketPersistenceRepository
from ai_trading_shared.utils.logging import get_logger
from market_data.domain.models import MarketFeatures, OHLCVBar
from market_data.infrastructure.repositories.memory import InMemoryMarketRepository

logger = get_logger(__name__)


class DualWriteMarketRepository:
    """Implements MarketRepositoryPort with optional durable SQL mirror."""

    def __init__(
        self,
        memory: Optional[InMemoryMarketRepository] = None,
        sql: Optional[MarketPersistenceRepository] = None,
    ) -> None:
        self._memory = memory or InMemoryMarketRepository()
        self._sql = sql

    async def upsert_bars(self, bars: List[OHLCVBar]) -> int:
        count = await self._memory.upsert_bars(bars)
        if self._sql is not None and bars:
            try:
                await self._sql.upsert_bars(
                    [
                        {
                            "ticker": b.ticker,
                            "asset_class": b.asset_class.value,
                            "timestamp": b.timestamp,
                            "open": b.open,
                            "high": b.high,
                            "low": b.low,
                            "close": b.close,
                            "volume": b.volume,
                            "vwap": b.vwap,
                        }
                        for b in bars
                    ]
                )
            except Exception:
                logger.exception("sql_bar_persist_failed")
        return count

    async def get_bars(self, ticker: str, limit: int = 60) -> List[OHLCVBar]:
        return await self._memory.get_bars(ticker, limit=limit)

    async def save_features(self, features: MarketFeatures) -> MarketFeatures:
        saved = await self._memory.save_features(features)
        if self._sql is not None:
            try:
                await self._sql.save_features(
                    {
                        "ticker": features.ticker,
                        "as_of": features.as_of,
                        "last_price": features.last_price,
                        "returns_1d": features.returns_1d,
                        "returns_5d": features.returns_5d,
                        "returns_20d": features.returns_20d,
                        "volatility_10d": features.volatility_10d,
                        "volatility_20d": features.volatility_20d,
                        "volume_zscore_20d": features.volume_zscore_20d,
                        "liquidity_score": features.liquidity_score,
                        "trend_strength": features.trend_strength,
                        "high_20d": features.high_20d,
                        "low_20d": features.low_20d,
                        "distance_from_high_20d": features.distance_from_high_20d,
                        "bars_used": features.bars_used,
                    }
                )
            except Exception:
                logger.exception("sql_feature_persist_failed")
        return saved

    async def get_features(self, ticker: str) -> Optional[MarketFeatures]:
        return await self._memory.get_features(ticker)

    async def list_tickers(self) -> List[str]:
        return await self._memory.list_tickers()
