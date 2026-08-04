"""Learning Engine domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field

from ai_trading_shared.domain.enums import DomainModel, SignalAction, new_id


class TradeOutcome(DomainModel):
    """Stores prediction vs realized result for a closed trade."""

    id: UUID = Field(default_factory=new_id)
    signal_id: UUID
    trade_id: Optional[UUID] = None
    ticker: str
    action: SignalAction
    predicted_direction: str  # up | down
    predicted_return: float
    probability_success: float
    confidence: float
    model_versions: List[str] = Field(default_factory=list)
    actual_return: float
    holding_days: int
    correct_direction: bool
    pnl: float
    closed_at: datetime = Field(default_factory=datetime.utcnow)
    notes: str = ""


class ModelAccuracyReport(DomainModel):
    model_name: str
    sample_size: int
    direction_accuracy: float
    avg_predicted_return: float
    avg_actual_return: float
    brier_score: float
    hit_rate_high_confidence: float
    suggestions: List[str] = Field(default_factory=list)
    breakdown: Dict[str, float] = Field(default_factory=dict)
