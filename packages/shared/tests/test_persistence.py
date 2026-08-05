"""Persistence repository tests using SQLite."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ai_trading_shared.domain.entities import Prediction
from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
from ai_trading_shared.infrastructure.repositories.persistence import (
    MarketPersistenceRepository,
    OutcomePersistenceRepository,
    PredictionPersistenceRepository,
)


@pytest.fixture
async def session_factory(tmp_path):
    from ai_trading_shared.infrastructure.db_models import (
        MarketBarRow,
        MarketFeatureRow,
        PredictionRow,
        TradeOutcomeRow,
    )

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: MarketBarRow.__table__.create(sync_conn, checkfirst=True)
        )
        await conn.run_sync(
            lambda sync_conn: MarketFeatureRow.__table__.create(sync_conn, checkfirst=True)
        )
        await conn.run_sync(
            lambda sync_conn: PredictionRow.__table__.create(sync_conn, checkfirst=True)
        )
        await conn.run_sync(
            lambda sync_conn: TradeOutcomeRow.__table__.create(sync_conn, checkfirst=True)
        )
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_market_features_roundtrip(session_factory) -> None:
    repo = MarketPersistenceRepository(session_factory)
    now = datetime.now(timezone.utc)
    await repo.upsert_bars(
        [
            {
                "ticker": "AAPL",
                "timestamp": now,
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 1e6,
            }
        ]
    )
    saved = await repo.save_features(
        {
            "ticker": "AAPL",
            "as_of": now,
            "last_price": 100.5,
            "returns_1d": 0.01,
            "returns_5d": 0.02,
            "returns_20d": 0.03,
            "volatility_10d": 0.2,
            "volatility_20d": 0.22,
            "volume_zscore_20d": 0.5,
            "liquidity_score": 0.7,
            "trend_strength": 0.1,
            "high_20d": 105,
            "low_20d": 95,
            "distance_from_high_20d": -0.04,
            "bars_used": 40,
        }
    )
    assert saved["ticker"] == "AAPL"
    loaded = await repo.get_features("AAPL")
    assert loaded is not None
    assert loaded["last_price"] == 100.5


@pytest.mark.asyncio
async def test_prediction_and_outcome_persist(session_factory) -> None:
    preds = PredictionPersistenceRepository(session_factory)
    outcomes = OutcomePersistenceRepository(session_factory)
    prediction = Prediction(
        ticker="NVDA",
        model_name="test",
        direction_prob_up=0.7,
        expected_return=0.03,
        volatility_forecast=0.3,
        trend_probability=0.6,
        mean_reversion_probability=0.4,
        breakout_probability=0.5,
        risk_score=0.3,
        horizon_days=5,
    )
    await preds.save(prediction)
    listed = await preds.list_recent(ticker="NVDA")
    assert len(listed) == 1

    saved = await outcomes.save(
        {
            "id": uuid4(),
            "signal_id": uuid4(),
            "ticker": "NVDA",
            "action": "buy",
            "predicted_direction": "up",
            "predicted_return": 0.03,
            "probability_success": 0.7,
            "confidence": 0.7,
            "model_versions": ["test"],
            "actual_return": 0.04,
            "holding_days": 5,
            "correct_direction": True,
            "pnl": 100.0,
        }
    )
    assert saved["correct"] is True
    rows = await outcomes.list_recent(ticker="NVDA")
    assert len(rows) == 1
