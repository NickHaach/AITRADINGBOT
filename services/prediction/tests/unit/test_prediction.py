"""Prediction engine tests."""

from __future__ import annotations

from prediction.ensemble import (
    EnsembleRouter,
    HeuristicEnsemble,
    TemperatureCalibrator,
    reliability_curve,
)


def test_heuristic_prediction() -> None:
    model = HeuristicEnsemble()
    pred = model.predict("NVDA", returns_5d=0.04, volatility_20d=0.35, sentiment_score=0.5)
    assert pred.ticker == "NVDA"
    assert 0 <= pred.direction_prob_up <= 1
    assert pred.volatility_forecast > 0


def test_calibrator_moves_extreme_probs_inward() -> None:
    cal = TemperatureCalibrator(temperature=2.0)
    assert cal.calibrate(0.9) < 0.9
    assert cal.calibrate(0.1) > 0.1


def test_ensemble_router_and_reliability() -> None:
    model = HeuristicEnsemble()
    p1 = model.predict("AAPL", 0.02, 0.2, 0.1)
    p2 = model.predict("AAPL", 0.01, 0.22, 0.0)
    combined = EnsembleRouter().combine([p1, p2])
    assert combined.model_name == "ensemble_router_v1"
    curve = reliability_curve([1, 0, 1, 1, 0], [0.8, 0.2, 0.7, 0.6, 0.3], bins=3)
    assert len(curve) >= 1
