"""Outcome ledger + calibrator tests."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from ai_trading_shared.domain.enums import SignalAction
from execution.outcomes import OutcomeLedger
from learning.calibration import refresh_calibrator
from learning.domain.models import TradeOutcome
from prediction.ensemble import TemperatureCalibrator


@pytest.mark.asyncio
async def test_ledger_closes_after_horizon() -> None:
    ledger = OutcomeLedger()
    ledger.advance_clock(1)
    ledger.register_fill(
        signal_id=uuid4(),
        trade_id=uuid4(),
        ticker="AAPL",
        action=SignalAction.BUY,
        predicted_return=0.02,
        direction_prob_up=0.7,
        direction_raw=0.8,
        confidence=0.7,
        model_versions=["heuristic_ensemble_v1"],
        entry_price=Decimal("100"),
        quantity=Decimal("10"),
        horizon_days=2,
    )
    # age 0 at same day
    closed = await ledger.close_matured({"AAPL": Decimal("110")})
    assert closed == []
    ledger.advance_clock(2)
    closed = await ledger.close_matured({"AAPL": Decimal("110")})
    assert len(closed) == 1
    assert closed[0].actual_return == pytest.approx(0.1)
    assert closed[0].probability_success == 0.7
    assert '"direction_raw": 0.8' in closed[0].notes or "0.8" in closed[0].notes
    assert ledger.open_lots == []


def test_temperature_fit_improves_overconfident() -> None:
    # Overconfident probs for mixed labels → higher T softens
    probs = [0.95] * 10 + [0.05] * 10
    labels = [1, 0] * 10
    cal = TemperatureCalibrator(temperature=1.0)
    before = TemperatureCalibrator(1.0)
    brier_before = sum((before.calibrate(p) - y) ** 2 for p, y in zip(probs, labels)) / len(probs)
    result = cal.fit(probs, labels)
    assert result["updated"] == 1.0
    assert result["samples"] == 20
    brier_after = result["brier"]
    assert brier_after <= brier_before + 1e-9


def test_refresh_calibrator_requires_samples() -> None:
    outcomes = [
        TradeOutcome(
            signal_id=uuid4(),
            ticker="AAPL",
            action=SignalAction.BUY,
            predicted_direction="up",
            predicted_return=0.02,
            probability_success=0.7,
            confidence=0.7,
            actual_return=0.01,
            holding_days=5,
            correct_direction=True,
            pnl=10,
            notes='{"direction_raw": 0.8}',
        )
        for _ in range(5)
    ]
    result = refresh_calibrator(outcomes, min_samples=30)
    assert result["updated"] == 0.0
    assert result["reason"] == "insufficient_samples"
