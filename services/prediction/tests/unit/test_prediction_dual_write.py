"""Prediction dual-write tests."""

from __future__ import annotations

from typing import List

import pytest

from ai_trading_shared.domain.entities import Prediction
from prediction.infrastructure.dual_write import DualWritePredictionStore


class FakePredSql:
    def __init__(self) -> None:
        self.saved: List[Prediction] = []

    async def save(self, prediction: Prediction) -> Prediction:
        self.saved.append(prediction)
        return prediction


@pytest.mark.asyncio
async def test_dual_write_mirrors_prediction() -> None:
    sql = FakePredSql()
    store = DualWritePredictionStore(sql=sql)
    pred = Prediction(
        ticker="AAPL",
        model_name="heuristic_ensemble_v1",
        direction_prob_up=0.62,
        expected_return=0.02,
        volatility_forecast=0.2,
        trend_probability=0.6,
        mean_reversion_probability=0.4,
        breakout_probability=0.5,
        risk_score=0.3,
        horizon_days=5,
    )
    await store.save(pred)
    assert len(sql.saved) == 1
    assert store.list_recent(ticker="AAPL")[0].ticker == "AAPL"


@pytest.mark.asyncio
async def test_dual_write_without_sql() -> None:
    store = DualWritePredictionStore()
    pred = Prediction(
        ticker="MSFT",
        model_name="heuristic_ensemble_v1",
        direction_prob_up=0.55,
        expected_return=0.01,
        volatility_forecast=0.18,
        trend_probability=0.5,
        mean_reversion_probability=0.5,
        breakout_probability=0.5,
        risk_score=0.4,
        horizon_days=5,
    )
    await store.save(pred)
    assert len(store.list_recent()) == 1
