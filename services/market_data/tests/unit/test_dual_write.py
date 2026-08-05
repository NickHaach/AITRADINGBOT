"""Dual-write market repository tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest

from market_data.application.service import MarketDataService
from market_data.domain.models import MarketFeatures, OHLCVBar
from market_data.infrastructure.adapters.mock_provider import MockMarketDataProvider
from market_data.infrastructure.repositories.dual_write import DualWriteMarketRepository
from market_data.infrastructure.repositories.memory import InMemoryMarketRepository


class FakeSqlMarketRepo:
    def __init__(self) -> None:
        self.bars: List[Dict[str, Any]] = []
        self.features: Optional[Dict[str, Any]] = None

    async def upsert_bars(self, bars: List[Dict[str, Any]]) -> int:
        self.bars.extend(bars)
        return len(bars)

    async def save_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        self.features = features
        return features


@pytest.mark.asyncio
async def test_dual_write_mirrors_to_sql() -> None:
    sql = FakeSqlMarketRepo()
    repo = DualWriteMarketRepository(memory=InMemoryMarketRepository(), sql=sql)
    service = MarketDataService(
        provider=MockMarketDataProvider(),
        repository=repo,
        default_tickers=["AAPL"],
    )
    await service.refresh_universe()
    assert len(sql.bars) > 0
    assert sql.features is not None
    assert sql.features["ticker"] == "AAPL"
    mem = await repo.get_features("AAPL")
    assert mem is not None


@pytest.mark.asyncio
async def test_dual_write_without_sql_still_works() -> None:
    repo = DualWriteMarketRepository()
    now = datetime.now(timezone.utc)
    features = MarketFeatures(
        ticker="MSFT",
        as_of=now,
        last_price=400.0,
        returns_1d=0.01,
        returns_5d=0.02,
        returns_20d=0.03,
        volatility_10d=0.2,
        volatility_20d=0.22,
        volume_zscore_20d=0.0,
        liquidity_score=0.8,
        trend_strength=0.1,
        high_20d=410,
        low_20d=390,
        distance_from_high_20d=-0.02,
        bars_used=40,
    )
    saved = await repo.save_features(features)
    assert saved.ticker == "MSFT"
    assert await repo.get_features("MSFT") is not None
