"""Trainable gradient-boosting direction model (sklearn; XGBoost optional)."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np

from ai_trading_shared.domain.entities import Prediction
from ai_trading_shared.domain.enums import new_id
from prediction.ensemble import TemperatureCalibrator, _clamp


FEATURE_NAMES = (
    "returns_5d",
    "volatility_20d",
    "sentiment_score",
    "announcement_impact",
    "liquidity_score",
    "trend_strength",
)


class GradientBoostDirectionModel:
    """Binary up/down classifier with probability outputs.

    Prefers XGBoost when installed; falls back to sklearn GradientBoosting.
    """

    name = "gbm_direction_v1"

    def __init__(self, calibrator: Optional[TemperatureCalibrator] = None) -> None:
        self.calibrator = calibrator or TemperatureCalibrator(temperature=1.1)
        self._model = None
        self._backend = "untrained"

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def fit(self, rows: Sequence[Tuple[Sequence[float], int]]) -> dict:
        if len(rows) < 10:
            raise ValueError("Need at least 10 labeled rows to train")
        x = np.array([r[0] for r in rows], dtype=np.float64)
        y = np.array([r[1] for r in rows], dtype=np.int64)
        if x.shape[1] != len(FEATURE_NAMES):
            raise ValueError(f"Expected {len(FEATURE_NAMES)} features")

        try:
            from xgboost import XGBClassifier

            model = XGBClassifier(
                n_estimators=80,
                max_depth=3,
                learning_rate=0.08,
                subsample=0.9,
                colsample_bytree=0.9,
                eval_metric="logloss",
                verbosity=0,
            )
            model.fit(x, y)
            self._backend = "xgboost"
        except Exception:
            from sklearn.ensemble import GradientBoostingClassifier

            model = GradientBoostingClassifier(
                n_estimators=80,
                max_depth=3,
                learning_rate=0.08,
            )
            model.fit(x, y)
            self._backend = "sklearn"
        self._model = model
        proba = model.predict_proba(x)[:, 1]
        pred = (proba >= 0.5).astype(int)
        acc = float(np.mean(pred == y))
        return {
            "backend": self._backend,
            "samples": int(len(rows)),
            "train_accuracy": round(acc, 4),
            "positive_rate": round(float(np.mean(y)), 4),
        }

    def predict_row(
        self,
        *,
        ticker: str,
        returns_5d: float,
        volatility_20d: float,
        sentiment_score: float = 0.0,
        announcement_impact: float = 0.0,
        liquidity_score: float = 0.5,
        trend_strength: float = 0.0,
        horizon_days: int = 5,
    ) -> Prediction:
        features = [
            returns_5d,
            volatility_20d,
            sentiment_score,
            announcement_impact,
            liquidity_score,
            trend_strength,
        ]
        if self._model is None:
            # cold start heuristic until trained
            raw = _clamp(0.5 + returns_5d * 1.5 + sentiment_score * 0.2 + announcement_impact * 0.15)
            backend = "cold_start"
        else:
            proba = self._model.predict_proba(np.array([features], dtype=np.float64))[0]
            # class 1 = up
            raw = float(proba[1] if len(proba) > 1 else proba[0])
            backend = self._backend

        direction = self.calibrator.calibrate(raw)
        expected = returns_5d * 0.35 + sentiment_score * 0.02 + announcement_impact * 0.03
        risk = _clamp(volatility_20d * 8.0)
        return Prediction(
            id=new_id(),
            ticker=ticker.upper(),
            model_name=f"{self.name}:{backend}",
            direction_prob_up=direction,
            expected_return=expected,
            volatility_forecast=max(volatility_20d, 0.001),
            trend_probability=_clamp(0.5 + trend_strength * 0.5),
            mean_reversion_probability=_clamp(0.5 - returns_5d * 2.0),
            breakout_probability=_clamp(0.4 + abs(returns_5d) * 3.0),
            risk_score=risk,
            horizon_days=horizon_days,
            features={
                **{name: value for name, value in zip(FEATURE_NAMES, features)},
                "direction_raw": raw,
            },
        )

    def predict(
        self,
        ticker: str,
        returns_5d: float,
        volatility_20d: float,
        sentiment_score: float = 0.0,
        announcement_impact: float = 0.0,
        horizon_days: int = 5,
    ) -> Prediction:
        """Ensemble-compatible predict surface for TradingPipeline."""
        return self.predict_row(
            ticker=ticker,
            returns_5d=returns_5d,
            volatility_20d=volatility_20d,
            sentiment_score=sentiment_score,
            announcement_impact=announcement_impact,
            liquidity_score=0.5,
            trend_strength=float(returns_5d) * 5.0,
            horizon_days=horizon_days,
        )


def synthesize_training_rows(n: int = 60, seed: int = 7) -> List[Tuple[List[float], int]]:
    """Synthetic labeled feature rows for offline unit tests."""
    rng = np.random.default_rng(seed)
    rows: List[Tuple[List[float], int]] = []
    for _ in range(n):
        returns_5d = float(rng.normal(0, 0.02))
        vol = float(abs(rng.normal(0.2, 0.05)))
        sentiment = float(np.clip(rng.normal(0, 0.4), -1, 1))
        impact = float(np.clip(rng.normal(0, 0.3), -1, 1))
        liquidity = float(np.clip(rng.uniform(0.2, 0.9), 0, 1))
        trend = float(np.clip(rng.normal(0, 0.3), -1, 1))
        # label correlated with momentum + sentiment
        score = returns_5d * 8 + sentiment * 0.5 + impact * 0.3 + rng.normal(0, 0.15)
        label = 1 if score > 0 else 0
        rows.append(([returns_5d, vol, sentiment, impact, liquidity, trend], label))
    return rows
