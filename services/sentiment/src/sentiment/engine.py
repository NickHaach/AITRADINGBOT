"""Sentiment Engine — multi-source composite sentiment scores."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ai_trading_shared.domain.enums import DomainModel, SentimentLabel, new_id

__version__ = "0.1.0"

BULLISH = ("beat", "upgrade", "rally", "surge", "bullish", "record", "strong")
BEARISH = ("miss", "downgrade", "plunge", "crash", "bearish", "fraud", "weak")


class SentimentSnapshot(DomainModel):
    id: UUID = Field(default_factory=new_id)
    ticker: str
    news_score: float
    analyst_score: float
    social_score: float
    insider_score: float
    institutional_score: float
    composite: float
    label: SentimentLabel
    as_of: datetime = Field(default_factory=datetime.utcnow)
    drivers: List[str] = Field(default_factory=list)


def score_text(text: str) -> float:
    lower = text.lower()
    bull = sum(1 for w in BULLISH if w in lower)
    bear = sum(1 for w in BEARISH if w in lower)
    total = bull + bear
    if total == 0:
        return 0.0
    return round((bull - bear) / total, 4)


def to_label(score: float) -> SentimentLabel:
    if score <= -0.6:
        return SentimentLabel.VERY_BEARISH
    if score <= -0.2:
        return SentimentLabel.BEARISH
    if score >= 0.6:
        return SentimentLabel.VERY_BULLISH
    if score >= 0.2:
        return SentimentLabel.BULLISH
    return SentimentLabel.NEUTRAL


class SentimentEngine:
    """Weighted composite of news / analyst / social / insider / institutional."""

    WEIGHTS = {
        "news": 0.30,
        "analyst": 0.25,
        "social": 0.15,
        "insider": 0.15,
        "institutional": 0.15,
    }

    def __init__(self) -> None:
        self._snapshots: Dict[str, SentimentSnapshot] = {}

    def score(
        self,
        ticker: str,
        *,
        news_text: str = "",
        analyst_text: str = "",
        social_text: str = "",
        insider_net_buys: float = 0.0,
        institutional_flow: float = 0.0,
    ) -> SentimentSnapshot:
        news = score_text(news_text)
        analyst = score_text(analyst_text)
        social = score_text(social_text)
        insider = float(max(-1.0, min(1.0, insider_net_buys)))
        institutional = float(max(-1.0, min(1.0, institutional_flow)))

        composite = (
            self.WEIGHTS["news"] * news
            + self.WEIGHTS["analyst"] * analyst
            + self.WEIGHTS["social"] * social
            + self.WEIGHTS["insider"] * insider
            + self.WEIGHTS["institutional"] * institutional
        )
        drivers = []
        for name, value in [
            ("news", news),
            ("analyst", analyst),
            ("social", social),
            ("insider", insider),
            ("institutional", institutional),
        ]:
            if abs(value) >= 0.2:
                drivers.append(f"{name}:{value:+.2f}")

        snap = SentimentSnapshot(
            ticker=ticker.upper(),
            news_score=news,
            analyst_score=analyst,
            social_score=social,
            insider_score=insider,
            institutional_score=institutional,
            composite=round(composite, 4),
            label=to_label(composite),
            drivers=drivers,
        )
        self._snapshots[snap.ticker] = snap
        return snap

    def get(self, ticker: str) -> Optional[SentimentSnapshot]:
        return self._snapshots.get(ticker.upper())

    def list_all(self) -> List[SentimentSnapshot]:
        return list(self._snapshots.values())


engine = SentimentEngine()
app = FastAPI(title="Sentiment Engine", version=__version__)


class ScoreRequest(BaseModel):
    ticker: str
    news_text: str = ""
    analyst_text: str = ""
    social_text: str = ""
    insider_net_buys: float = Field(0.0, ge=-1.0, le=1.0)
    institutional_flow: float = Field(0.0, ge=-1.0, le=1.0)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "sentiment"}


@app.post("/v1/sentiment/score")
async def score(body: ScoreRequest) -> dict:
    snap = engine.score(
        body.ticker,
        news_text=body.news_text,
        analyst_text=body.analyst_text,
        social_text=body.social_text,
        insider_net_buys=body.insider_net_buys,
        institutional_flow=body.institutional_flow,
    )
    return snap.model_dump(mode="json")


@app.get("/v1/sentiment/{ticker}")
async def get_sentiment(ticker: str) -> dict:
    snap = engine.get(ticker)
    if snap is None:
        raise HTTPException(status_code=404, detail="No sentiment for ticker")
    return snap.model_dump(mode="json")
