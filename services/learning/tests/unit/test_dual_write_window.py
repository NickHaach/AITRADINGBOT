"""Learning dual-write and rolling-window tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from ai_trading_shared.domain.enums import SignalAction
from learning.application.engine import LearningEngine
from learning.domain.models import TradeOutcome
from learning.infrastructure.dual_write import DualWriteLearningStore


class FakeOutcomeSql:
    def __init__(self) -> None:
        self.saved: List[Dict[str, Any]] = []

    async def save(self, outcome: Dict[str, Any]) -> Dict[str, Any]:
        self.saved.append(outcome)
        return {"id": str(outcome["id"]), "ticker": outcome["ticker"], "correct": outcome["correct_direction"]}


def _record(engine: LearningEngine, pred: float, actual: float, *, days_ago: int = 0, model: str = "m1") -> None:
    closed = datetime.now(timezone.utc) - timedelta(days=days_ago)
    outcome = TradeOutcome(
        signal_id=uuid4(),
        trade_id=uuid4(),
        ticker="AAPL",
        action=SignalAction.BUY,
        predicted_direction="up" if pred >= 0 else "down",
        predicted_return=pred,
        probability_success=0.7 if pred >= 0 else 0.3,
        confidence=0.7,
        model_versions=[model],
        actual_return=actual,
        holding_days=5,
        correct_direction=(pred >= 0 and actual >= 0) or (pred < 0 and actual < 0),
        pnl=actual * 1000,
        closed_at=closed,
    )
    engine.record(outcome)


def test_window_days_filters_old_outcomes() -> None:
    engine = LearningEngine()
    _record(engine, 0.02, 0.01, days_ago=2)
    _record(engine, 0.03, 0.02, days_ago=20)
    report = engine.evaluate(window_days=7)
    assert report.sample_size == 1


def test_promotion_thresholds() -> None:
    empty = LearningEngine().evaluate()
    assert LearningEngine.meets_promotion_thresholds(empty) is False

    engine = LearningEngine()
    for _ in range(30):
        _record(engine, 0.02, 0.01)
    report = engine.evaluate()
    assert report.sample_size == 30
    assert LearningEngine.meets_promotion_thresholds(report) is True


@pytest.mark.asyncio
async def test_dual_write_mirrors_outcome() -> None:
    sql = FakeOutcomeSql()
    store = DualWriteLearningStore(sql=sql)
    await store.record_closed_trade(
        signal_id=uuid4(),
        trade_id=uuid4(),
        ticker="NVDA",
        action=SignalAction.BUY,
        predicted_return=0.04,
        probability_success=0.7,
        confidence=0.7,
        model_versions=["heuristic_ensemble_v1"],
        actual_return=0.03,
        holding_days=5,
        pnl=30.0,
    )
    assert len(sql.saved) == 1
    assert sql.saved[0]["ticker"] == "NVDA"
    assert store.list_outcomes(ticker="NVDA")
