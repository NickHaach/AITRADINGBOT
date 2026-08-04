"""Market data domain models and ports."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Protocol
from uuid import UUID

from pydantic import Field

from ai_trading_shared.domain.enums import AssetClass, DomainModel, new_id


class OHLCVBar(DomainModel):
    ticker: str
    asset_class: AssetClass = AssetClass.STOCK
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    vwap: Optional[Decimal] = None


class Quote(DomainModel):
    ticker: str
    bid: Decimal
    ask: Decimal
    bid_size: Decimal = Decimal("0")
    ask_size: Decimal = Decimal("0")
    last: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OrderBookLevel(DomainModel):
    price: Decimal
    size: Decimal


class OrderBookSnapshot(DomainModel):
    ticker: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def mid(self) -> Optional[Decimal]:
        if not self.bids or not self.asks:
            return None
        return (self.bids[0].price + self.asks[0].price) / Decimal("2")

    @property
    def spread(self) -> Optional[Decimal]:
        if not self.bids or not self.asks:
            return None
        return self.asks[0].price - self.bids[0].price


class MarketFeatures(DomainModel):
    """Derived features consumed by Prediction / Risk engines."""

    id: UUID = Field(default_factory=new_id)
    ticker: str
    as_of: datetime
    last_price: float
    returns_1d: float
    returns_5d: float
    returns_20d: float
    volatility_10d: float
    volatility_20d: float
    volume_zscore_20d: float
    liquidity_score: float = Field(ge=0.0, le=1.0)
    trend_strength: float = Field(ge=-1.0, le=1.0)
    high_20d: float
    low_20d: float
    distance_from_high_20d: float
    bars_used: int


class MarketDataPort(Protocol):
    name: str

    async def fetch_ohlcv(
        self,
        ticker: str,
        *,
        lookback_days: int = 60,
        asset_class: AssetClass = AssetClass.STOCK,
    ) -> List[OHLCVBar]:
        ...

    async def fetch_quote(self, ticker: str) -> Quote:
        ...


class MarketRepositoryPort(Protocol):
    async def upsert_bars(self, bars: List[OHLCVBar]) -> int:
        ...

    async def get_bars(self, ticker: str, limit: int = 60) -> List[OHLCVBar]:
        ...

    async def save_features(self, features: MarketFeatures) -> MarketFeatures:
        ...

    async def get_features(self, ticker: str) -> Optional[MarketFeatures]:
        ...

    async def list_tickers(self) -> List[str]:
        ...
