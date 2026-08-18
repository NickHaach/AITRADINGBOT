"""News Intelligence FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_trading_shared.config import Settings, get_settings
from ai_trading_shared.domain.enums import NewsCategory
from ai_trading_shared.utils.logging import configure_logging, get_logger
from news_intelligence.application.classifier import LexiconNewsClassifier
from news_intelligence.application.ingest import IngestNewsService
from news_intelligence.infrastructure.adapters.mock_feed import MockNewsFeed
from news_intelligence.infrastructure.adapters.newsapi_feed import NewsApiFeed
from news_intelligence.infrastructure.embeddings.store import InMemoryEmbeddingStore
from news_intelligence.infrastructure.repositories.news_repository import InMemoryNewsRepository

logger = get_logger(__name__)


class NewsArticleResponse(BaseModel):
    id: UUID
    source: str
    title: str
    body: str
    url: str | None
    published_at: str
    category: str
    countries: list[str]
    sectors: list[str]
    companies: list[str]
    risk_level: str
    sentiment: str
    sentiment_score: float
    confidence: float
    urgency: str


class IngestResponse(BaseModel):
    ingested: int
    articles: list[NewsArticleResponse]


class SemanticHit(BaseModel):
    id: str
    score: float
    payload: dict = Field(default_factory=dict)


def build_ingest_service(settings: Settings) -> IngestNewsService:
    feeds: list = [MockNewsFeed()]
    if not settings.use_mock_news and settings.newsapi_key is not None:
        key = settings.newsapi_key.get_secret_value()
        if key:
            feeds.append(NewsApiFeed(api_key=key))
    return IngestNewsService(
        feeds=feeds,
        repository=InMemoryNewsRepository(),
        classifier=LexiconNewsClassifier(),
        embeddings=InMemoryEmbeddingStore(),
        event_bus=None,
    )


_service: IngestNewsService | None = None


def get_service() -> IngestNewsService:
    if _service is None:
        raise RuntimeError("Service not initialized")
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _service
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    _service = build_ingest_service(settings)
    # warm cache with an initial ingest cycle
    await _service.run_cycle()
    logger.info("news_intelligence_started")
    yield
    logger.info("news_intelligence_stopped")


app = FastAPI(
    title="News Intelligence Engine",
    version="0.1.0",
    lifespan=lifespan,
)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "news_intelligence"}


@app.post("/v1/news/ingest", response_model=IngestResponse)
async def ingest_news(
    service: Annotated[IngestNewsService, Depends(get_service)],
) -> IngestResponse:
    articles = await service.run_cycle()
    return IngestResponse(
        ingested=len(articles),
        articles=[_to_response(a) for a in articles],
    )


@app.get("/v1/news", response_model=list[NewsArticleResponse])
async def list_news(
    service: Annotated[IngestNewsService, Depends(get_service)],
    limit: int = Query(50, ge=1, le=200),
    category: NewsCategory | None = None,
) -> list[NewsArticleResponse]:
    articles = await service.list_recent(limit=limit, category=category)
    return [_to_response(a) for a in articles]


@app.get("/v1/news/{article_id}", response_model=NewsArticleResponse)
async def get_news(
    article_id: UUID,
    service: Annotated[IngestNewsService, Depends(get_service)],
) -> NewsArticleResponse:
    article = await service.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return _to_response(article)


@app.get("/v1/news/search/semantic", response_model=list[SemanticHit])
async def semantic_search(
    service: Annotated[IngestNewsService, Depends(get_service)],
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
) -> list[SemanticHit]:
    hits = await service.semantic_search(q, limit=limit)
    return [SemanticHit.model_validate(h) for h in hits]


def _to_response(article) -> NewsArticleResponse:
    return NewsArticleResponse(
        id=article.id,
        source=article.source,
        title=article.title,
        body=article.body,
        url=article.url,
        published_at=article.published_at.isoformat(),
        category=article.category.value,
        countries=article.countries,
        sectors=article.sectors,
        companies=article.companies,
        risk_level=article.risk_level.value,
        sentiment=article.sentiment.value,
        sentiment_score=article.sentiment_score,
        confidence=article.confidence,
        urgency=article.urgency.value,
    )
