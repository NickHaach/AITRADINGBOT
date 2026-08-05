"""Pipeline closes lots into learning outcomes."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from ai_trading_shared.domain.enums import SignalAction
from execution.pipeline import TradingPipeline
from learning.infrastructure.dual_write import DualWriteLearningStore


@pytest.mark.asyncio
async def test_pipeline_registers_and_closes_lots() -> None:
    store = DualWriteLearningStore()
    pipeline = TradingPipeline(learning_store=store, paper_days_per_cycle=1)
    # Force an open lot as if a buy filled
    pipeline.outcome_ledger.advance_clock(1)
    pipeline.outcome_ledger.register_fill(
        signal_id=uuid4(),
        trade_id=uuid4(),
        ticker="AAPL",
        action=SignalAction.BUY,
        predicted_return=0.03,
        direction_prob_up=0.65,
        direction_raw=0.72,
        confidence=0.7,
        model_versions=["heuristic_ensemble_v1"],
        entry_price=Decimal("100"),
        quantity=Decimal("5"),
        horizon_days=1,
    )
    # Next cycle advances clock and closes
    result = await pipeline.run_once(["AAPL"])
    assert result["closed_outcomes"] >= 1
    assert store.list_outcomes(ticker="AAPL")
    assert "calibration" in result
