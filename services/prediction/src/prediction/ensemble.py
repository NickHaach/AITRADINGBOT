"""Prediction Engine — ensemble forecasting with confidence calibration."""

from __future__ import annotations

from statistics import mean
from typing import Dict, List, Optional, Sequence

from ai_trading_shared.domain.entities import Prediction
from ai_trading_shared.domain.enums import new_id

__version__ = "0.1.0"


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


class TemperatureCalibrator:
    """Simple temperature scaling for probability calibration."""

    def __init__(self, temperature: float = 1.2) -> None:
        if temperature <= 0:
            raise ValueError("temperature must be > 0")
        self.temperature = temperature

    def calibrate(self, probability: float) -> float:
        # Map through logits-ish transform without numpy dependency here
        p = _clamp(probability, 1e-6, 1 - 1e-6)
        # logit
        from math import exp, log

        logit = log(p / (1 - p)) / self.temperature
        return _clamp(1.0 / (1.0 + exp(-logit)))


class HeuristicEnsemble:
    """Baseline ensemble combining trend / mean-reversion / breakout heuristics."""

    def __init__(self, calibrator: Optional[TemperatureCalibrator] = None) -> None:
        self.calibrator = calibrator or TemperatureCalibrator()

    def predict(
        self,
        ticker: str,
        returns_5d: float,
        volatility_20d: float,
        sentiment_score: float = 0.0,
        announcement_impact: float = 0.0,
        horizon_days: int = 5,
    ) -> Prediction:
        trend = _clamp(0.5 + returns_5d * 2.0)
        mean_rev = _clamp(0.5 - returns_5d * 2.0)
        breakout = _clamp(0.4 + abs(returns_5d) * 3.0 + (0.1 if volatility_20d > 0.03 else 0))
        direction_raw = _clamp(
            0.5 + returns_5d * 1.5 + sentiment_score * 0.2 + announcement_impact * 0.15
        )
        direction = self.calibrator.calibrate(direction_raw)
        expected = returns_5d * 0.4 + sentiment_score * 0.02 + announcement_impact * 0.03
        risk = _clamp(volatility_20d * 8.0 + (0.2 if abs(sentiment_score) > 0.5 else 0))

        return Prediction(
            id=new_id(),
            ticker=ticker.upper(),
            model_name="heuristic_ensemble_v1",
            direction_prob_up=direction,
            expected_return=expected,
            volatility_forecast=max(volatility_20d, 0.001),
            trend_probability=trend,
            mean_reversion_probability=mean_rev,
            breakout_probability=breakout,
            risk_score=risk,
            horizon_days=horizon_days,
            features={
                "returns_5d": returns_5d,
                "volatility_20d": volatility_20d,
                "sentiment_score": sentiment_score,
                "announcement_impact": announcement_impact,
                "direction_raw": direction_raw,
                "blend": mean([trend, mean_rev, breakout]),
            },
        )


class EnsembleRouter:
    """Average multiple model predictions for a ticker."""

    def combine(self, predictions: Sequence[Prediction]) -> Prediction:
        if not predictions:
            raise ValueError("No predictions to combine")
        if len(predictions) == 1:
            return predictions[0]
        ticker = predictions[0].ticker
        return Prediction(
            id=new_id(),
            ticker=ticker,
            model_name="ensemble_router_v1",
            direction_prob_up=mean(p.direction_prob_up for p in predictions),
            expected_return=mean(p.expected_return for p in predictions),
            volatility_forecast=mean(p.volatility_forecast for p in predictions),
            trend_probability=mean(p.trend_probability for p in predictions),
            mean_reversion_probability=mean(p.mean_reversion_probability for p in predictions),
            breakout_probability=mean(p.breakout_probability for p in predictions),
            risk_score=mean(p.risk_score for p in predictions),
            horizon_days=predictions[0].horizon_days,
            features={"members": [p.model_name for p in predictions]},
        )


def reliability_curve(
    y_true: Sequence[int], y_prob: Sequence[float], bins: int = 5
) -> List[Dict[str, float]]:
    """Compute a simple calibration reliability curve."""
    if len(y_true) != len(y_prob) or not y_true:
        raise ValueError("y_true and y_prob must be equal non-empty length")
    edges = [i / bins for i in range(bins + 1)]
    curve: List[Dict[str, float]] = []
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        idxs = [j for j, p in enumerate(y_prob) if (p >= lo and (p < hi or (i == bins - 1 and p <= hi)))]
        if not idxs:
            continue
        avg_prob = mean(y_prob[j] for j in idxs)
        freq = mean(y_true[j] for j in idxs)
        curve.append(
            {
                "bin_left": lo,
                "bin_right": hi,
                "avg_predicted": round(avg_prob, 4),
                "empirical_frequency": round(freq, 4),
                "count": float(len(idxs)),
            }
        )
    return curve
