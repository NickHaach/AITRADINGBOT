"""Pipeline prediction/portfolio persistence tests."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from ai_trading_shared.domain.entities import Prediction
from execution.pipeline import TradingPipeline
from prediction.infrastructure.dual_write import DualWritePredictionStore


class FakePredSql:
    def __init__(self) -> None:
        self.saved: List[Prediction] = []

    async def save(self, prediction: Prediction) -> Prediction:
        self.saved.append(prediction)
        return prediction


class FakePortfolioSql:
    def __init__(self) -> None:
        self.saved: List[Dict[str, Any]] = []

    async def save(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        self.saved.append(snapshot)
        return snapshot


@pytest.mark.asyncio
async def test_run_once_persists_predictions_and_snapshot() -> None:
    pred_sql = FakePredSql()
    port_sql = FakePortfolioSql()
    pipeline = TradingPipeline(
        prediction_store=DualWritePredictionStore(sql=pred_sql),
        portfolio_writer=port_sql,
    )
    result = await pipeline.run_once(["AAPL", "MSFT"])
    assert result["signals"] >= 2
    assert len(pred_sql.saved) >= 2
    assert len(port_sql.saved) == 1
    book = pipeline.latest_snapshot_payload()
    assert book["equity"] > 0
    assert "positions" in book
