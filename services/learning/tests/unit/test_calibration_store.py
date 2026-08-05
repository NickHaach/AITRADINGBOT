"""Calibration store memory + mocked Redis tests."""

from __future__ import annotations

from uuid import uuid4

from ai_trading_shared.domain.enums import SignalAction
from learning import calibration as cal_mod
from learning.domain.models import TradeOutcome
from prediction.ensemble import TemperatureCalibrator


def test_last_fit_falls_back_to_memory(monkeypatch) -> None:
    cal_mod._LAST_FIT = {"temperature": 1.7, "brier": 0.1, "samples": 40.0, "updated": 1.0}

    class FakeStore:
        def get_json(self, key):
            return None

        def set_json(self, key, value, ttl_seconds=None):
            return False

    monkeypatch.setattr(cal_mod, "_store", lambda: FakeStore())
    assert cal_mod.last_fit()["temperature"] == 1.7


def test_refresh_writes_memory_and_redis(monkeypatch) -> None:
    written = {}

    class FakeStore:
        def get_json(self, key):
            return written.get(key)

        def set_json(self, key, value, ttl_seconds=None):
            written[key] = value
            return True

    monkeypatch.setattr(cal_mod, "_store", lambda: FakeStore())
    outcomes = [
        TradeOutcome(
            signal_id=uuid4(),
            ticker="AAPL",
            action=SignalAction.BUY,
            predicted_direction="up",
            predicted_return=0.02,
            probability_success=0.9,
            confidence=0.8,
            actual_return=0.01 if i % 2 == 0 else -0.01,
            holding_days=5,
            correct_direction=i % 2 == 0,
            pnl=10,
            notes='{"direction_raw": 0.9}',
        )
        for i in range(30)
    ]
    result = cal_mod.refresh_calibrator(
        outcomes, calibrator=TemperatureCalibrator(1.0), min_samples=30
    )
    assert result["updated"] == 1.0
    from ai_trading_shared.infrastructure.redis_kv import CALIBRATION_KEY

    assert CALIBRATION_KEY in written
    assert cal_mod.last_fit()["temperature"] == written[CALIBRATION_KEY]["temperature"]
