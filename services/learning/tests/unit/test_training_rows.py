"""Training row rebuild from outcomes."""

from __future__ import annotations

import json
from uuid import uuid4

from ai_trading_shared.domain.enums import SignalAction
from learning.domain.models import TradeOutcome
from learning.training_rows import outcome_to_training_row, outcomes_to_training_rows


def test_outcome_to_training_row() -> None:
    features = {
        "returns_5d": 0.02,
        "volatility_20d": 0.2,
        "sentiment_score": 0.1,
        "announcement_impact": 0.0,
        "liquidity_score": 0.7,
        "trend_strength": 0.3,
    }
    outcome = TradeOutcome(
        signal_id=uuid4(),
        ticker="AAPL",
        action=SignalAction.BUY,
        predicted_direction="up",
        predicted_return=0.02,
        probability_success=0.6,
        confidence=0.7,
        actual_return=0.03,
        holding_days=5,
        correct_direction=True,
        pnl=30,
        notes=json.dumps({"features": features, "direction_raw": 0.7}),
    )
    row = outcome_to_training_row(outcome)
    assert row is not None
    assert row[0] == [0.02, 0.2, 0.1, 0.0, 0.7, 0.3]
    assert row[1] == 1


def test_skips_incomplete_features() -> None:
    outcome = TradeOutcome(
        signal_id=uuid4(),
        ticker="AAPL",
        action=SignalAction.BUY,
        predicted_direction="up",
        predicted_return=0.02,
        probability_success=0.6,
        confidence=0.7,
        actual_return=-0.01,
        holding_days=5,
        correct_direction=False,
        pnl=-10,
        notes=json.dumps({"features": {"returns_5d": 0.01}}),
    )
    assert outcome_to_training_row(outcome) is None
    assert outcomes_to_training_rows([outcome]) == []
