"""Dual-write learning store: memory for speed, optional SQL for durability."""

from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from ai_trading_shared.domain.enums import SignalAction
from ai_trading_shared.infrastructure.repositories.persistence import OutcomePersistenceRepository
from ai_trading_shared.utils.logging import get_logger
from learning.application.engine import LearningEngine
from learning.domain.models import ModelAccuracyReport, TradeOutcome

logger = get_logger(__name__)


class DualWriteLearningStore:
    """Wraps LearningEngine with optional OutcomePersistenceRepository mirror."""

    def __init__(
        self,
        engine: Optional[LearningEngine] = None,
        sql: Optional[OutcomePersistenceRepository] = None,
    ) -> None:
        self.engine = engine or LearningEngine()
        self._sql = sql

    async def record_closed_trade(
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
        outcome = self.engine.record_closed_trade(
            signal_id=signal_id,
            trade_id=trade_id,
            ticker=ticker,
            action=action,
            predicted_return=predicted_return,
            probability_success=probability_success,
            confidence=confidence,
            model_versions=model_versions,
            actual_return=actual_return,
            holding_days=holding_days,
            pnl=pnl,
            notes=notes,
        )
        if self._sql is not None:
            try:
                await self._sql.save(
                    {
                        "id": outcome.id,
                        "signal_id": outcome.signal_id,
                        "trade_id": outcome.trade_id,
                        "ticker": outcome.ticker,
                        "action": outcome.action.value,
                        "predicted_direction": outcome.predicted_direction,
                        "predicted_return": outcome.predicted_return,
                        "probability_success": outcome.probability_success,
                        "confidence": outcome.confidence,
                        "model_versions": outcome.model_versions,
                        "actual_return": outcome.actual_return,
                        "holding_days": outcome.holding_days,
                        "correct_direction": outcome.correct_direction,
                        "pnl": outcome.pnl,
                        "closed_at": outcome.closed_at,
                        "notes": outcome.notes,
                    }
                )
            except Exception:
                logger.exception("sql_outcome_persist_failed")
        return outcome

    def list_outcomes(self, ticker: Optional[str] = None, limit: int = 100) -> List[TradeOutcome]:
        return self.engine.list_outcomes(ticker=ticker, limit=limit)

    def evaluate(
        self,
        model_name: str = "all",
        *,
        window_days: Optional[int] = None,
    ) -> ModelAccuracyReport:
        return self.engine.evaluate(model_name, window_days=window_days)
