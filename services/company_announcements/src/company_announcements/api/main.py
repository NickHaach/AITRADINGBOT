"""Company Announcements FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_trading_shared.config import get_settings
from ai_trading_shared.utils.logging import configure_logging, get_logger
from company_announcements.application.extractor import LexiconAnnouncementExtractor
from company_announcements.application.ingest import AnnouncementIngestService
from company_announcements.infrastructure.adapters.mock_feed import MockFilingFeed
from company_announcements.infrastructure.repositories.memory import InMemoryAnnouncementRepository

logger = get_logger(__name__)
_service: Optional[AnnouncementIngestService] = None


class AnnouncementResponse(BaseModel):
    id: UUID
    company_ticker: str
    filing_type: str
    title: str
    summary: Optional[str]
    impact_score: float
    revenue: Optional[float]
    eps: Optional[float]
    margins: Optional[float]
    forward_guidance: Optional[str]
    risks: List[str]
    opportunities: List[str]
    filed_at: str
    source: str


def build_service() -> AnnouncementIngestService:
    return AnnouncementIngestService(
        feeds=[MockFilingFeed()],
        extractor=LexiconAnnouncementExtractor(),
        repository=InMemoryAnnouncementRepository(),
    )


def get_service() -> AnnouncementIngestService:
    if _service is None:
        raise RuntimeError("Announcement service not initialized")
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _service
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    _service = build_service()
    await _service.run_cycle()
    logger.info("company_announcements_started")
    yield


app = FastAPI(title="Company Announcement Engine", version="0.1.0", lifespan=lifespan)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "company_announcements"}


@app.post("/v1/announcements/ingest", response_model=List[AnnouncementResponse])
async def ingest(service: Annotated[AnnouncementIngestService, Depends(get_service)]) -> List[AnnouncementResponse]:
    items = await service.run_cycle()
    return [_to_response(a) for a in items]


@app.get("/v1/announcements", response_model=List[AnnouncementResponse])
async def list_announcements(
    service: Annotated[AnnouncementIngestService, Depends(get_service)],
    limit: int = Query(50, ge=1, le=200),
    ticker: Optional[str] = None,
) -> List[AnnouncementResponse]:
    items = await service.list_recent(limit=limit, ticker=ticker)
    return [_to_response(a) for a in items]


@app.get("/v1/announcements/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: UUID,
    service: Annotated[AnnouncementIngestService, Depends(get_service)],
) -> AnnouncementResponse:
    item = await service.get(announcement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return _to_response(item)


def _dec(value: Optional[Decimal]) -> Optional[float]:
    return float(value) if value is not None else None


def _to_response(a) -> AnnouncementResponse:
    return AnnouncementResponse(
        id=a.id,
        company_ticker=a.company_ticker,
        filing_type=a.filing_type,
        title=a.title,
        summary=a.summary,
        impact_score=a.impact_score,
        revenue=_dec(a.revenue),
        eps=_dec(a.eps),
        margins=_dec(a.margins),
        forward_guidance=a.forward_guidance,
        risks=a.risks,
        opportunities=a.opportunities,
        filed_at=a.filed_at.isoformat(),
        source=a.source,
    )
