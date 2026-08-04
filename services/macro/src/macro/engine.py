"""Macroeconomic Engine — indicators, calendar events, expected reactions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from ai_trading_shared.domain.enums import DomainModel, new_id

__version__ = "0.1.0"


class MacroIndicator(DomainModel):
    id: UUID = Field(default_factory=new_id)
    name: str
    country: str
    value: float
    previous: Optional[float] = None
    consensus: Optional[float] = None
    unit: str = ""
    released_at: datetime
    surprise: Optional[float] = None


class MacroEvent(DomainModel):
    id: UUID = Field(default_factory=new_id)
    title: str
    country: str
    category: str
    scheduled_at: datetime
    importance: str = "medium"
    actual: Optional[float] = None
    consensus: Optional[float] = None
    previous: Optional[float] = None


class MacroReaction(DomainModel):
    event_id: UUID
    expected_asset_moves: Dict[str, float]
    narrative: str
    confidence: float


# Surprise → typical asset reaction templates (directional, not guarantees)
REACTION_TEMPLATES: Dict[str, Dict[str, float]] = {
    "inflation_hot": {"TLT": -0.8, "GLD": 0.3, "USD": 0.4, "SPY": -0.5},
    "inflation_cool": {"TLT": 0.6, "SPY": 0.4, "USD": -0.2},
    "jobs_strong": {"USD": 0.5, "TLT": -0.4, "SPY": 0.2},
    "jobs_weak": {"TLT": 0.5, "USD": -0.4, "SPY": -0.3},
    "gdp_strong": {"SPY": 0.4, "USD": 0.2},
    "gdp_weak": {"TLT": 0.4, "SPY": -0.4},
    "rate_hike": {"TLT": -1.0, "USD": 0.6, "SPY": -0.6, "XLF": -0.3},
    "rate_cut": {"TLT": 0.8, "SPY": 0.5, "USD": -0.5},
}


class MacroEngine:
    def __init__(self) -> None:
        self._indicators: List[MacroIndicator] = []
        self._events: List[MacroEvent] = []
        self._seed()

    def _seed(self) -> None:
        now = datetime.now(timezone.utc)
        self._indicators = [
            MacroIndicator(
                name="CPI YoY",
                country="US",
                value=3.2,
                previous=3.4,
                consensus=3.3,
                unit="%",
                released_at=now - timedelta(days=2),
                surprise=-0.1,
            ),
            MacroIndicator(
                name="Unemployment Rate",
                country="US",
                value=4.1,
                previous=4.0,
                consensus=4.0,
                unit="%",
                released_at=now - timedelta(days=5),
                surprise=0.1,
            ),
            MacroIndicator(
                name="GDP QoQ Annualized",
                country="US",
                value=2.8,
                previous=3.0,
                consensus=2.5,
                unit="%",
                released_at=now - timedelta(days=10),
                surprise=0.3,
            ),
            MacroIndicator(
                name="Fed Funds Rate",
                country="US",
                value=5.25,
                previous=5.25,
                consensus=5.25,
                unit="%",
                released_at=now - timedelta(days=15),
                surprise=0.0,
            ),
            MacroIndicator(
                name="ISM Manufacturing PMI",
                country="US",
                value=48.5,
                previous=49.0,
                consensus=49.2,
                unit="index",
                released_at=now - timedelta(days=3),
                surprise=-0.7,
            ),
        ]
        self._events = [
            MacroEvent(
                title="FOMC Rate Decision",
                country="US",
                category="central_bank",
                scheduled_at=now + timedelta(days=12),
                importance="high",
                consensus=5.25,
                previous=5.25,
            ),
            MacroEvent(
                title="US CPI Release",
                country="US",
                category="inflation",
                scheduled_at=now + timedelta(days=6),
                importance="high",
                consensus=3.1,
                previous=3.2,
            ),
            MacroEvent(
                title="Nonfarm Payrolls",
                country="US",
                category="employment",
                scheduled_at=now + timedelta(days=9),
                importance="high",
                consensus=180000,
                previous=175000,
            ),
        ]

    def list_indicators(self, country: Optional[str] = None) -> List[MacroIndicator]:
        items = self._indicators
        if country:
            items = [i for i in items if i.country.upper() == country.upper()]
        return sorted(items, key=lambda i: i.released_at, reverse=True)

    def list_calendar(self, days: int = 30) -> List[MacroEvent]:
        cutoff = datetime.now(timezone.utc) + timedelta(days=days)
        now = datetime.now(timezone.utc) - timedelta(days=1)
        return sorted(
            [e for e in self._events if now <= e.scheduled_at <= cutoff],
            key=lambda e: e.scheduled_at,
        )

    def estimate_reaction(self, indicator: MacroIndicator) -> MacroReaction:
        name = indicator.name.lower()
        surprise = indicator.surprise if indicator.surprise is not None else 0.0
        key = "gdp_strong"
        if "cpi" in name or "inflation" in name:
            key = "inflation_hot" if surprise > 0 else "inflation_cool"
        elif "unemployment" in name or "payroll" in name or "nfp" in name:
            # higher unemployment = weak jobs
            key = "jobs_weak" if surprise > 0 else "jobs_strong"
        elif "gdp" in name:
            key = "gdp_strong" if surprise >= 0 else "gdp_weak"
        elif "fed funds" in name or "rate" in name:
            key = "rate_hike" if surprise > 0 else "rate_cut" if surprise < 0 else "gdp_strong"
        elif "pmi" in name:
            key = "gdp_weak" if indicator.value < 50 else "gdp_strong"

        moves = {k: round(v * (0.5 + min(abs(surprise), 1.0)), 3) for k, v in REACTION_TEMPLATES[key].items()}
        return MacroReaction(
            event_id=indicator.id,
            expected_asset_moves=moves,
            narrative=f"{indicator.name} surprise={surprise}; template={key}",
            confidence=min(0.45 + abs(surprise) * 0.2, 0.85),
        )


engine = MacroEngine()
app = FastAPI(title="Macroeconomic Engine", version=__version__)


class IndicatorOut(BaseModel):
    id: UUID
    name: str
    country: str
    value: float
    previous: Optional[float]
    consensus: Optional[float]
    surprise: Optional[float]
    released_at: str


class ReactionOut(BaseModel):
    event_id: UUID
    expected_asset_moves: Dict[str, float]
    narrative: str
    confidence: float


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "macro"}


@app.get("/v1/macro/indicators", response_model=List[IndicatorOut])
async def indicators(country: Optional[str] = None) -> List[IndicatorOut]:
    return [
        IndicatorOut(
            id=i.id,
            name=i.name,
            country=i.country,
            value=i.value,
            previous=i.previous,
            consensus=i.consensus,
            surprise=i.surprise,
            released_at=i.released_at.isoformat(),
        )
        for i in engine.list_indicators(country)
    ]


@app.get("/v1/macro/calendar")
async def calendar(days: int = Query(30, ge=1, le=90)) -> List[dict]:
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "country": e.country,
            "category": e.category,
            "scheduled_at": e.scheduled_at.isoformat(),
            "importance": e.importance,
            "consensus": e.consensus,
            "previous": e.previous,
        }
        for e in engine.list_calendar(days)
    ]


@app.get("/v1/macro/indicators/{indicator_id}/reaction", response_model=ReactionOut)
async def reaction(indicator_id: UUID) -> ReactionOut:
    match = next((i for i in engine.list_indicators() if i.id == indicator_id), None)
    if match is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Indicator not found")
    r = engine.estimate_reaction(match)
    return ReactionOut(
        event_id=r.event_id,
        expected_asset_moves=r.expected_asset_moves,
        narrative=r.narrative,
        confidence=r.confidence,
    )
