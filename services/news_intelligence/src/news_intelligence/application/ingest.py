"""Ingest and classify news use case."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ai_trading_shared.domain.entities import NewsArticle
from ai_trading_shared.domain.enums import NewsCategory, RiskLevel, SentimentLabel, Urgency, new_id
from ai_trading_shared.events import STREAM_NEWS, NewsClassified, NewsIngested
from ai_trading_shared.infrastructure.redis_bus import RedisEventBus
from ai_trading_shared.utils.logging import get_logger
from news_intelligence.domain.dedupe import content_hash
from news_intelligence.domain.ports import (
    ClassifierPort,
    EmbeddingPort,
    NewsFeedPort,
    NewsRepositoryPort,
    RawNewsItem,
)

logger = get_logger(__name__)


class IngestNewsService:
    """Orchestrates fetch → dedupe → classify → embed → persist → publish."""

    def __init__(
        self,
        feeds: list[NewsFeedPort],
        repository: NewsRepositoryPort,
        classifier: ClassifierPort,
        embeddings: EmbeddingPort,
        event_bus: RedisEventBus | None = None,
    ) -> None:
        self._feeds = feeds
        self._repo = repository
        self._classifier = classifier
        self._embeddings = embeddings
        self._bus = event_bus

    async def run_cycle(self, since: datetime | None = None, limit_per_feed: int = 50) -> list[NewsArticle]:
        ingested: list[NewsArticle] = []
        for feed in self._feeds:
            try:
                items = await feed.fetch_since(since=since, limit=limit_per_feed)
            except Exception:
                logger.exception("feed_fetch_failed", feed=feed.name)
                continue
            for item in items:
                article = await self.process_item(item)
                if article is not None:
                    ingested.append(article)
        logger.info("ingest_cycle_complete", count=len(ingested))
        return ingested

    async def process_item(self, item: RawNewsItem) -> NewsArticle | None:
        digest = content_hash(item.title, item.body)
        if await self._repo.exists_by_hash(digest):
            logger.debug("duplicate_skipped", source=item.source, external_id=item.external_id)
            return None

        classification = await self._classifier.classify(item.title, item.body)
        article_id = new_id()
        embedding_id = str(article_id)

        vectors = await self._embeddings.embed([f"{item.title}\n{item.body}"])
        if vectors:
            await self._embeddings.upsert_vectors(
                ids=[embedding_id],
                vectors=vectors,
                payloads=[
                    {
                        "article_id": embedding_id,
                        "title": item.title,
                        "source": item.source,
                        "category": classification["category"].value
                        if hasattr(classification["category"], "value")
                        else str(classification["category"]),
                        "companies": classification["companies"],
                    }
                ],
            )

        article = NewsArticle(
            id=article_id,
            external_id=item.external_id,
            source=item.source,
            title=item.title,
            body=item.body,
            url=item.url,
            published_at=item.published_at,
            language=item.language,
            content_hash=digest,
            category=_as_enum(classification["category"], NewsCategory),
            countries=list(classification["countries"]),
            sectors=list(classification["sectors"]),
            companies=list(classification["companies"]),
            industries=list(classification["industries"]),
            risk_level=_as_enum(classification["risk_level"], RiskLevel),
            sentiment=_as_enum(classification["sentiment"], SentimentLabel),
            sentiment_score=float(classification["sentiment_score"]),
            confidence=float(classification["confidence"]),
            urgency=_as_enum(classification["urgency"], Urgency),
            embedding_id=embedding_id,
        )
        saved = await self._repo.upsert(article)

        if self._bus is not None:
            await self._bus.publish(
                STREAM_NEWS,
                NewsIngested(payload={"article_id": str(saved.id), "source": saved.source}),
            )
            await self._bus.publish(
                STREAM_NEWS,
                NewsClassified(
                    payload={
                        "article_id": str(saved.id),
                        "category": saved.category.value,
                        "sentiment": saved.sentiment.value,
                        "risk_level": saved.risk_level.value,
                        "companies": saved.companies,
                        "confidence": saved.confidence,
                    }
                ),
            )
        return saved

    async def get_article(self, article_id: UUID) -> NewsArticle | None:
        return await self._repo.get(article_id)

    async def list_recent(
        self, limit: int = 50, category: NewsCategory | None = None
    ) -> list[NewsArticle]:
        return await self._repo.list_recent(limit=limit, category=category)

    async def semantic_search(self, query: str, limit: int = 10) -> list[dict]:
        vectors = await self._embeddings.embed([query])
        if not vectors:
            return []
        return await self._embeddings.search(vectors[0], limit=limit)


def _as_enum(value: object, enum_cls: type) -> object:
    if isinstance(value, enum_cls):
        return value
    return enum_cls(value)
