"""Backtesting domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field

from ai_trading_shared.domain.enums import DomainModel, new_id


class BacktestBar(DomainModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class NewsEvent(DomainModel):
    timestamp: datetime
    ticker: str
    sentiment_score: float
    headline: str = ""


class BacktestTrade(DomainModel):
    timestamp: datetime
    side: str
    price: float
    quantity: float
    reason: str = ""


class BacktestResult(DomainModel):
    id: UUID = Field(default_factory=new_id)
    strategy_name: str
    ticker: str
    started_at: datetime
    ended_at: datetime
    initial_cash: float
    final_equity: float
    total_return: float
    max_drawdown: float
    sharpe: float
    win_rate: float
    trade_count: int
    equity_curve: List[float] = Field(default_factory=list)
    trades: List[BacktestTrade] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)
    notes: Optional[str] = None
