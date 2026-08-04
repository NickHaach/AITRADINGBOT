"""Backtesting FastAPI application."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backtesting.application.engine import BacktestEngine, MomentumNewsStrategy
from backtesting.domain.models import BacktestBar, NewsEvent

engine = BacktestEngine()
app = FastAPI(title="Backtesting Engine", version="0.1.0")


class BarIn(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class NewsIn(BaseModel):
    timestamp: datetime
    ticker: str
    sentiment_score: float
    headline: str = ""


class RunRequest(BaseModel):
    ticker: str
    bars: List[BarIn] = Field(min_length=10)
    news: List[NewsIn] = Field(default_factory=list)
    initial_cash: float = 100_000.0
    lookback: int = 5


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "backtesting"}


@app.post("/v1/backtests/run")
async def run_backtest(body: RunRequest) -> dict:
    local = BacktestEngine(initial_cash=body.initial_cash)
    result = local.run(
        ticker=body.ticker,
        bars=[BacktestBar(**b.model_dump()) for b in body.bars],
        strategy=MomentumNewsStrategy(lookback=body.lookback),
        news=[NewsEvent(**n.model_dump()) for n in body.news],
    )
    engine._results.append(result)
    return result.model_dump(mode="json")


@app.get("/v1/backtests")
async def list_backtests() -> List[dict]:
    return [r.model_dump(mode="json") for r in engine.list_results()]


@app.get("/v1/backtests/{backtest_id}")
async def get_backtest(backtest_id: UUID) -> dict:
    match = next((r for r in engine.list_results() if r.id == backtest_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return match.model_dump(mode="json")
