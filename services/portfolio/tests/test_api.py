"""Portfolio desk API tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ai_trading_shared.config import Settings
from portfolio.api import main as portfolio_main
from portfolio.api.main import app, build_pipeline


@pytest.mark.asyncio
async def test_portfolio_endpoints() -> None:
    settings = Settings(enable_sql_persistence=False, use_mock_market_data=True)
    pipeline = build_pipeline(settings)
    await pipeline.run_once(["AAPL", "NVDA"])
    portfolio_main._pipeline = pipeline

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        assert health.status_code == 200
        book = await client.get("/v1/portfolio")
        assert book.status_code == 200
        payload = book.json()
        assert "equity" in payload
        assert "positions" in payload
        hist = await client.get("/v1/portfolio/history")
        assert hist.status_code == 200
        assert isinstance(hist.json(), list)
        recs = await client.get("/v1/portfolio/recommendations")
        assert recs.status_code == 200
