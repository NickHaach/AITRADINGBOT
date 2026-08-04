"""Learning engine unit tests."""

from __future__ import annotations

from uuid import uuid4

from ai_trading_shared.domain.enums import SignalAction
from learning.application.engine import LearningEngine


def test_records_and_evaluates_accuracy() -> None:
    engine = LearningEngine()
    # 3 correct, 1 wrong
    samples = [
        (0.04, 0.05, True),
        (0.03, 0.02, True),
        (-0.02, -0.01, True),
        (0.05, -0.03, False),
    ]
    for pred, actual, _ in samples:
        engine.record_closed_trade(
            signal_id=uuid4(),
            trade_id=uuid4(),
            ticker="NVDA",
            action=SignalAction.BUY,
            predicted_return=pred,
            probability_success=0.7 if pred > 0 else 0.3,
            confidence=0.7,
            model_versions=["heuristic_ensemble_v1"],
            actual_return=actual,
            holding_days=5,
            pnl=actual * 1000,
        )
    report = engine.evaluate("heuristic_ensemble_v1")
    assert report.sample_size == 4
    assert report.direction_accuracy == 0.75
    assert report.suggestions
    assert "NVDA" in report.breakdown


def test_empty_report_suggestion() -> None:
    report = LearningEngine().evaluate()
    assert report.sample_size == 0
    assert "Collect" in report.suggestions[0]
