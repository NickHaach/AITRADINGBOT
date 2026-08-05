"""Dual-write prediction store: memory buffer + optional SQL persistence."""

from __future__ import annotations

from typing import List, Optional

from ai_trading_shared.domain.entities import Prediction
from ai_trading_shared.infrastructure.repositories.persistence import PredictionPersistenceRepository
from ai_trading_shared.utils.logging import get_logger

logger = get_logger(__name__)


class DualWritePredictionStore:
    """Keeps recent predictions in memory and optionally mirrors to SQL."""

    def __init__(
        self,
        sql: Optional[PredictionPersistenceRepository] = None,
        *,
        max_memory: int = 500,
    ) -> None:
        self._sql = sql
        self._memory: List[Prediction] = []
        self._max = max_memory

    async def save(self, prediction: Prediction) -> Prediction:
        self._memory.append(prediction)
        if len(self._memory) > self._max:
            self._memory = self._memory[-self._max :]
        if self._sql is not None:
            try:
                await self._sql.save(prediction)
            except Exception:
                logger.exception("sql_prediction_persist_failed", ticker=prediction.ticker)
        return prediction

    def list_recent(self, ticker: Optional[str] = None, limit: int = 50) -> List[Prediction]:
        items = self._memory
        if ticker:
            items = [p for p in items if p.ticker == ticker.upper()]
        return list(reversed(items[-limit:]))
