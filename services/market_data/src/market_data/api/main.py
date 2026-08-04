"""Market Data FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from ai_trading_shared.config import Settings, get_settings
from ai_trading_shared.utils.logging import configure_logging, get_logger
from market_data.application.service import MarketDataService
from market_data.infrastructure.adapters.mock_provider import MockMarketDataProvider
from market_data.infrastructure.adapters.polygon_provider import PolygonMarketDataProvider
from market_data.infrastructure.repositories.memory import InMemoryMarketRepository

logger = get_logger(__name__)
_service: Optional[MarketDataService] = None


class FeaturesResponse(BaseModel):
    ticker: str
    as_of: str
    last_price: float
    returns_1d: float
    returns_5d: float
    returns_20d: float
    volatility_10d: float
    volatility_20d: float
    volume_zscore_20d: float
    liquidity_score: float
    trend_strength: float
    high_20d: float
    low_20d: float
    distance_from_high_20d: float
    bars_used: int


class BarResponse(BaseModel):
    ticker: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class QuoteResponse(BaseModel):
    ticker: str
    bid: float
    ask: float
    last: float
    timestamp: str


def build_service(settings: Settings) -> MarketDataService:
    if settings.use_mock_market_data or settings.polygon_api_key is None:
        provider = MockMarketDataProvider()
    else:
        key = settings.polygon_api_key.get_secret_value()
        provider = PolygonMarketDataProvider(api_key=key) if key else MockMarketDataProvider()
    return MarketDataService(provider=provider, repository=InMemoryMarketRepository())


def get_service() -> MarketDataService:
    if _service is None:
        raise RuntimeError("Market data service not initialized")
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _service
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    _service = build_service(settings)
    await _service.refresh_universe()
    logger.info("market_data_started")
    yield


app = FastAPI(title="Market Data Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "market_data"}


@app.post("/v1/market/refresh", response_model=List[FeaturesResponse])
async def refresh_universe(
    service: Annotated[MarketDataService, Depends(get_service)],
    tickers: Optional[str] = Query(None, description="Comma-separated tickers"),
) -> List[FeaturesResponse]:
    parsed = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    features = await service.refresh_universe(parsed)
    return [_features(f) for f in features]


@app.post("/v1/market/{ticker}/refresh", response_model=FeaturesResponse)
async def refresh_ticker(
    ticker: str,
    service: Annotated[MarketDataService, Depends(get_service)],
) -> FeaturesResponse:
    features = await service.refresh_ticker(ticker.upper())
    return _features(features)


@app.get("/v1/market/{ticker}/features", response_model=FeaturesResponse)
async def get_features(
    ticker: str,
    service: Annotated[MarketDataService, Depends(get_service)],
) -> FeaturesResponse:
    features = await service.get_features(ticker.upper())
    if features is None:
        raise HTTPException(status_code=404, detail="Features not found; refresh first")
    return _features(features)


@app.get("/v1/market/{ticker}/bars", response_model=List[BarResponse])
async def get_bars(
    ticker: str,
    service: Annotated[MarketDataService, Depends(get_service)],
    limit: int = Query(60, ge=5, le=500),
) -> List[BarResponse]:
    bars = await service.get_bars(ticker.upper(), limit=limit)
    return [
        BarResponse(
            ticker=b.ticker,
            timestamp=b.timestamp.isoformat(),
            open=float(b.open),
            high=float(b.high),
            low=float(b.low),
            close=float(b.close),
            volume=float(b.volume),
        )
        for b in bars
    ]


@app.get("/v1/market/{ticker}/quote", response_model=QuoteResponse)
async def get_quote(
    ticker: str,
    service: Annotated[MarketDataService, Depends(get_service)],
) -> QuoteResponse:
    q = await service.get_quote(ticker.upper())
    return QuoteResponse(
        ticker=q.ticker,
        bid=float(q.bid),
        ask=float(q.ask),
        last=float(q.last),
        timestamp=q.timestamp.isoformat(),
    )


@app.get("/v1/market/tickers")
async def list_tickers(service: Annotated[MarketDataService, Depends(get_service)]) -> List[str]:
    return await service.list_tickers()


def _features(f) -> FeaturesResponse:
    return FeaturesResponse(
        ticker=f.ticker,
        as_of=f.as_of.isoformat(),
        last_price=f.last_price,
        returns_1d=f.returns_1d,
        returns_5d=f.returns_5d,
        returns_20d=f.returns_20d,
        volatility_10d=f.volatility_10d,
        volatility_20d=f.volatility_20d,
        volume_zscore_20d=f.volume_zscore_20d,
        liquidity_score=f.liquidity_score,
        trend_strength=f.trend_strength,
        high_20d=f.high_20d,
        low_20d=f.low_20d,
        distance_from_high_20d=f.distance_from_high_20d,
        bars_used=f.bars_used,
    )
