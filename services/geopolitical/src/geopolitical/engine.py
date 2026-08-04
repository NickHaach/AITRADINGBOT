"""Geopolitical Intelligence Engine — conflict/sanctions impact mapping."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ai_trading_shared.domain.enums import DomainModel, RiskLevel, new_id

__version__ = "0.1.0"

ASSET_CHANNELS = (
    "oil",
    "gold",
    "defense",
    "shipping",
    "semiconductors",
    "agriculture",
    "currencies",
    "interest_rates",
)


class GeoEvent(DomainModel):
    id: UUID = Field(default_factory=new_id)
    title: str
    event_type: str
    countries: List[str]
    severity: RiskLevel
    summary: str
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    impacts: Dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.55


IMPACT_TEMPLATES: Dict[str, Dict[str, float]] = {
    "war": {
        "oil": 0.8,
        "gold": 0.7,
        "defense": 0.9,
        "shipping": 0.6,
        "semiconductors": -0.3,
        "agriculture": 0.5,
        "currencies": -0.4,
        "interest_rates": 0.2,
    },
    "sanctions": {
        "oil": 0.5,
        "gold": 0.3,
        "defense": 0.2,
        "shipping": 0.4,
        "semiconductors": -0.6,
        "agriculture": 0.2,
        "currencies": -0.3,
        "interest_rates": 0.1,
    },
    "tariff": {
        "oil": 0.1,
        "gold": 0.1,
        "defense": 0.0,
        "shipping": -0.2,
        "semiconductors": -0.7,
        "agriculture": -0.4,
        "currencies": 0.2,
        "interest_rates": 0.1,
    },
    "shipping": {
        "oil": 0.4,
        "gold": 0.1,
        "defense": 0.2,
        "shipping": 0.9,
        "semiconductors": -0.2,
        "agriculture": 0.5,
        "currencies": -0.1,
        "interest_rates": 0.0,
    },
    "election": {
        "oil": 0.0,
        "gold": 0.2,
        "defense": 0.1,
        "shipping": 0.0,
        "semiconductors": 0.1,
        "agriculture": 0.0,
        "currencies": 0.3,
        "interest_rates": 0.2,
    },
}


class GeopoliticalEngine:
    def __init__(self) -> None:
        self._events: List[GeoEvent] = [
            GeoEvent(
                title="Red Sea shipping disruptions intensify",
                event_type="shipping",
                countries=["YE", "EG", "SA"],
                severity=RiskLevel.HIGH,
                summary="Attacks disrupt container and energy tanker routes via Bab el-Mandeb.",
                impacts=IMPACT_TEMPLATES["shipping"],
                confidence=0.7,
            ),
            GeoEvent(
                title="Expanded sanctions on energy exports",
                event_type="sanctions",
                countries=["RU", "US", "EU"],
                severity=RiskLevel.HIGH,
                summary="New sanctions package targets energy and dual-use technology.",
                impacts=IMPACT_TEMPLATES["sanctions"],
                confidence=0.65,
            ),
            GeoEvent(
                title="US-China semiconductor tariff escalation",
                event_type="tariff",
                countries=["US", "CN"],
                severity=RiskLevel.MEDIUM,
                summary="Tariff proposals threaten chip supply chain costs and margins.",
                impacts=IMPACT_TEMPLATES["tariff"],
                confidence=0.6,
            ),
        ]

    def list_events(self, event_type: Optional[str] = None) -> List[GeoEvent]:
        items = self._events
        if event_type:
            items = [e for e in items if e.event_type == event_type]
        return items

    def assess(self, title: str, event_type: str, countries: List[str], severity: RiskLevel) -> GeoEvent:
        base = IMPACT_TEMPLATES.get(event_type, IMPACT_TEMPLATES["election"])
        scale = {
            RiskLevel.LOW: 0.4,
            RiskLevel.MEDIUM: 0.7,
            RiskLevel.HIGH: 1.0,
            RiskLevel.CRITICAL: 1.25,
        }[severity]
        impacts = {k: round(max(-1.0, min(1.0, v * scale)), 3) for k, v in base.items()}
        event = GeoEvent(
            title=title,
            event_type=event_type,
            countries=countries,
            severity=severity,
            summary=f"Assessed {event_type} event involving {', '.join(countries)}.",
            impacts=impacts,
            confidence=min(0.5 + scale * 0.25, 0.9),
        )
        self._events.insert(0, event)
        return event


engine = GeopoliticalEngine()
app = FastAPI(title="Geopolitical Intelligence Engine", version=__version__)


class AssessRequest(BaseModel):
    title: str
    event_type: str = Field(pattern="^(war|sanctions|tariff|shipping|election)$")
    countries: List[str]
    severity: RiskLevel = RiskLevel.MEDIUM


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "geopolitical"}


@app.get("/v1/geo/events")
async def list_events(event_type: Optional[str] = None) -> List[dict]:
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "event_type": e.event_type,
            "countries": e.countries,
            "severity": e.severity.value,
            "summary": e.summary,
            "impacts": e.impacts,
            "confidence": e.confidence,
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in engine.list_events(event_type)
    ]


@app.post("/v1/geo/assess")
async def assess(body: AssessRequest) -> dict:
    event = engine.assess(body.title, body.event_type, body.countries, body.severity)
    return {
        "id": str(event.id),
        "title": event.title,
        "impacts": event.impacts,
        "confidence": event.confidence,
        "severity": event.severity.value,
    }


@app.get("/v1/geo/events/{event_id}")
async def get_event(event_id: UUID) -> dict:
    match = next((e for e in engine.list_events() if e.id == event_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return {
        "id": str(match.id),
        "title": match.title,
        "impacts": match.impacts,
        "channels": list(ASSET_CHANNELS),
    }
