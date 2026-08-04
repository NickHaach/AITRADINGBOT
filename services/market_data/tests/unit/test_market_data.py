"""Unit tests for Market Data Engine."""

from __future__ import annotations

import pytest

from market_data.application.features import compute_features
from market_data.application.service import MarketDataService
from market_data.infrastructure.adapters.mock_provider import MockMarketDataProvider
from market_data.infrastructure.repositories.memory import InMemoryMarketRepository


@pytest.mark.asyncio
async def test_mock_provider_returns_bars() -> None:
    provider = MockMarketDataProvider()
    bars = await provider.fetch_ohlcv("NVDA", lookback_days=30)
    assert len(bars) == 30
    assert bars[0].timestamp < bars[-1].timestamp
    assert bars[-1].close > 0


@pytest.mark.asyncio
async def test_compute_features_from_mock() -> None:
    provider = MockMarketDataProvider()
    bars = await provider.fetch_ohlcv("AAPL", lookback_days=40)
    features = compute_features(bars)
    assert features.ticker == "AAPL"
    assert features.bars_used == 40
    assert features.volatility_20d >= 0
    assert 0 <= features.liquidity_score <= 1
    assert -1 <= features.trend_strength <= 1


@pytest.mark.asyncio
async def test_features_require_minimum_bars() -> None:
    provider = MockMarketDataProvider()
    bars = await provider.fetch_ohlcv("SPY", lookback_days=5)
    with pytest.raises(ValueError):
        compute_features(bars[:3])



@pytest.mark.asyncio
async def test_service_refresh_and_lookup() -> None:
    service = MarketDataService(
        provider=MockMarketDataProvider(),
        repository=InMemoryMarketRepository(),
        default_tickers=["MSFT", "XOM"],
    )
    refreshed = await service.refresh_universe()
    assert len(refreshed) == 2
    features = await service.get_features("MSFT")
    assert features is not None
    bars = await service.get_bars("MSFT", limit=10)
    assert len(bars) == 10
    quote = await service.get_quote("MSFT")
    assert quote.ask >= quote.bid


@pytest.mark.asyncio
async def test_deterministic_mock_seed() -> None:
    a = MockMarketDataProvider()
    b = MockMarketDataProvider()
    bars_a = await a.fetch_ohlcv("QQQ", lookback_days=20)
    bars_b = await b.fetch_ohlcv("QQQ", lookback_days=20)
    assert [float(x.close) for x in bars_a] == [float(x.close) for x in bars_b]
