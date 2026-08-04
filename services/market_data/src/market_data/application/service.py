"""Market data ingest and feature refresh use case."""

from __future__ import annotations

from typing import List, Optional, Sequence

from ai_trading_shared.domain.enums import AssetClass
from ai_trading_shared.events import STREAM_MARKET, DomainEvent
from ai_trading_shared.infrastructure.redis_bus import RedisEventBus
from ai_trading_shared.utils.logging import get_logger
from market_data.application.features import compute_features
from market_data.domain.models import MarketFeatures, MarketDataPort, MarketRepositoryPort, OHLCVBar, Quote

logger = get_logger(__name__)


class MarketDataService:
    """Fetch bars from adapters, store them, and refresh derived features."""

    def __init__(
        self,
        provider: MarketDataPort,
        repository: MarketRepositoryPort,
        event_bus: Optional[RedisEventBus] = None,
        default_tickers: Optional[Sequence[str]] = None,
    ) -> None:
        self._provider = provider
        self._repo = repository
        self._bus = event_bus
        self._default_tickers = list(default_tickers or ["AAPL", "MSFT", "NVDA", "SPY", "QQQ", "XOM", "JPM"])

    async def refresh_ticker(
        self,
        ticker: str,
        *,
        lookback_days: int = 60,
        asset_class: AssetClass = AssetClass.STOCK,
    ) -> MarketFeatures:
        bars = await self._provider.fetch_ohlcv(
            ticker, lookback_days=lookback_days, asset_class=asset_class
        )
        if not bars:
            raise ValueError(f"No bars returned for {ticker}")
        await self._repo.upsert_bars(bars)
        features = compute_features(bars)
        saved = await self._repo.save_features(features)
        if self._bus is not None:
            await self._bus.publish(
                STREAM_MARKET,
                DomainEvent(
                    event_type="market.features_updated",
                    payload={
                        "ticker": saved.ticker,
                        "last_price": saved.last_price,
                        "volatility_20d": saved.volatility_20d,
                        "returns_5d": saved.returns_5d,
                    },
                ),
            )
        logger.info("market_features_refreshed", ticker=ticker, bars=len(bars))
        return saved

    async def refresh_universe(self, tickers: Optional[Sequence[str]] = None) -> List[MarketFeatures]:
        targets = list(tickers or self._default_tickers)
        results: List[MarketFeatures] = []
        for ticker in targets:
            try:
                results.append(await self.refresh_ticker(ticker))
            except Exception:
                logger.exception("ticker_refresh_failed", ticker=ticker)
        return results

    async def get_features(self, ticker: str) -> Optional[MarketFeatures]:
        return await self._repo.get_features(ticker)

    async def get_bars(self, ticker: str, limit: int = 60) -> List[OHLCVBar]:
        return await self._repo.get_bars(ticker, limit=limit)

    async def get_quote(self, ticker: str) -> Quote:
        return await self._provider.fetch_quote(ticker)

    async def list_tickers(self) -> List[str]:
        return await self._repo.list_tickers()
