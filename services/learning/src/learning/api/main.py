"""Learning Engine FastAPI app."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from ai_trading_shared.domain.enums import SignalAction
from learning.application.engine import LearningEngine

engine = LearningEngine()
app = FastAPI(title="Learning Engine", version="0.1.0")


class RecordRequest(BaseModel):
    signal_id: UUID
    trade_id: Optional[UUID] = None
    ticker: str
    action: SignalAction
    predicted_return: float
    probability_success: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    model_versions: List[str] = Field(default_factory=list)
    actual_return: float
    holding_days: int = Field(ge=0)
    pnl: float
    notes: str = ""


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "learning"}


@app.post("/v1/learning/outcomes")
async def record_outcome(body: RecordRequest) -> dict:
    outcome = engine.record_closed_trade(**body.model_dump())
    return outcome.model_dump(mode="json")


@app.get("/v1/learning/outcomes")
async def list_outcomes(
    ticker: Optional[str] = None, limit: int = Query(50, ge=1, le=500)
) -> List[dict]:
    return [o.model_dump(mode="json") for o in engine.list_outcomes(ticker=ticker, limit=limit)]


@app.get("/v1/learning/report")
async def report(model_name: str = "all") -> dict:
    return engine.evaluate(model_name).model_dump(mode="json")
