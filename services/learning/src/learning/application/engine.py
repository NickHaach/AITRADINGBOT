"""Learning Engine — record outcomes and measure prediction quality."""

from __future__ import annotations

from statistics import mean
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from ai_trading_shared.domain.enums import SignalAction
from ai_trading_shared.utils.logging import get_logger
from learning.domain.models import ModelAccuracyReport, TradeOutcome

logger = get_logger(__name__)


class LearningEngine:
    """Compares predictions to realized outcomes and emits improvement hints."""

    def __init__(self) -> None:
        self._outcomes: List[TradeOutcome] = []

    def record(self, outcome: TradeOutcome) -> TradeOutcome:
        self._outcomes.append(outcome)
        logger.info(
            "outcome_recorded",
            ticker=outcome.ticker,
            correct=outcome.correct_direction,
            actual_return=outcome.actual_return,
        )
        return outcome

    def record_closed_trade(
        self,
        *,
        signal_id: UUID,
        trade_id: Optional[UUID],
        ticker: str,
        action: SignalAction,
        predicted_return: float,
        probability_success: float,
        confidence: float,
        model_versions: Sequence[str],
        actual_return: float,
        holding_days: int,
        pnl: float,
        notes: str = "",
    ) -> TradeOutcome:
        predicted_direction = "up" if predicted_return >= 0 else "down"
        correct = (actual_return == 0 and predicted_return == 0) or (
            actual_return > 0 and predicted_return > 0
        ) or (actual_return < 0 and predicted_return < 0)

        outcome = TradeOutcome(
            signal_id=signal_id,
            trade_id=trade_id,
            ticker=ticker.upper(),
            action=action,
            predicted_direction=predicted_direction,
            predicted_return=predicted_return,
            probability_success=probability_success,
            confidence=confidence,
            model_versions=list(model_versions),
            actual_return=actual_return,
            holding_days=holding_days,
            correct_direction=correct,
            pnl=pnl,
            notes=notes,
        )
        return self.record(outcome)

    def list_outcomes(self, ticker: Optional[str] = None, limit: int = 100) -> List[TradeOutcome]:
        items = self._outcomes
        if ticker:
            items = [o for o in items if o.ticker == ticker.upper()]
        return list(reversed(items[-limit:]))

    def evaluate(self, model_name: str = "all") -> ModelAccuracyReport:
        outcomes = self._outcomes
        if model_name != "all":
            outcomes = [o for o in outcomes if model_name in o.model_versions]
        if not outcomes:
            return ModelAccuracyReport(
                model_name=model_name,
                sample_size=0,
                direction_accuracy=0.0,
                avg_predicted_return=0.0,
                avg_actual_return=0.0,
                brier_score=0.0,
                hit_rate_high_confidence=0.0,
                suggestions=["Collect closed-trade outcomes before evaluating models."],
            )

        direction_acc = mean(1.0 if o.correct_direction else 0.0 for o in outcomes)
        avg_pred = mean(o.predicted_return for o in outcomes)
        avg_act = mean(o.actual_return for o in outcomes)
        # Brier for directional probability vs binary up-move
        brier = mean(
            (o.probability_success - (1.0 if o.actual_return > 0 else 0.0)) ** 2 for o in outcomes
        )
        high_conf = [o for o in outcomes if o.confidence >= 0.65]
        hit_high = (
            mean(1.0 if o.correct_direction else 0.0 for o in high_conf) if high_conf else 0.0
        )

        by_ticker: Dict[str, float] = {}
        tickers = sorted({o.ticker for o in outcomes})
        for t in tickers:
            subset = [o for o in outcomes if o.ticker == t]
            by_ticker[t] = round(mean(1.0 if o.correct_direction else 0.0 for o in subset), 4)

        suggestions = self._suggestions(direction_acc, brier, hit_high, avg_pred, avg_act, len(outcomes))
        return ModelAccuracyReport(
            model_name=model_name,
            sample_size=len(outcomes),
            direction_accuracy=round(direction_acc, 4),
            avg_predicted_return=round(avg_pred, 6),
            avg_actual_return=round(avg_act, 6),
            brier_score=round(brier, 4),
            hit_rate_high_confidence=round(hit_high, 4),
            suggestions=suggestions,
            breakdown=by_ticker,
        )

    @staticmethod
    def _suggestions(
        direction_acc: float,
        brier: float,
        hit_high: float,
        avg_pred: float,
        avg_act: float,
        n: int,
    ) -> List[str]:
        tips: List[str] = []
        if n < 30:
            tips.append("Increase sample size to ≥30 closed trades for stable metrics.")
        if direction_acc < 0.52:
            tips.append("Direction accuracy near chance — raise signal confidence threshold or retrain.")
        if brier > 0.25:
            tips.append("Poor probability calibration — apply temperature scaling / isotonic regression.")
        if hit_high < direction_acc:
            tips.append("High-confidence trades underperform — audit confidence features for overconfidence.")
        if abs(avg_pred - avg_act) > 0.01:
            tips.append(
                f"Return bias detected (pred {avg_pred:.3%} vs actual {avg_act:.3%}) — recalibrate expected-return model."
            )
        if direction_acc >= 0.58 and brier <= 0.2:
            tips.append("Metrics healthy — consider modestly increasing position size within risk caps.")
        if not tips:
            tips.append("No critical issues detected; continue monitoring rolling windows.")
        return tips
