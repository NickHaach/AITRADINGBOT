"""GBM direction model tests."""

from __future__ import annotations

from prediction.gbm_model import GradientBoostDirectionModel, synthesize_training_rows


def test_gbm_trains_and_predicts() -> None:
    model = GradientBoostDirectionModel()
    rows = synthesize_training_rows(80)
    metrics = model.fit(rows)
    assert metrics["samples"] == 80
    assert metrics["train_accuracy"] >= 0.55
    assert model.is_trained
    pred = model.predict_row(
        ticker="AAPL",
        returns_5d=0.03,
        volatility_20d=0.2,
        sentiment_score=0.4,
        announcement_impact=0.2,
        liquidity_score=0.7,
        trend_strength=0.3,
    )
    assert pred.ticker == "AAPL"
    assert 0 <= pred.direction_prob_up <= 1
    assert "gbm_direction_v1" in pred.model_name


def test_cold_start_predict_without_fit() -> None:
    model = GradientBoostDirectionModel()
    pred = model.predict_row(ticker="MSFT", returns_5d=0.01, volatility_20d=0.15)
    assert "cold_start" in pred.model_name
