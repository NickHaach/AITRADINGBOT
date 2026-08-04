"""In-memory and SQLAlchemy news repositories."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_shared.domain.entities import NewsArticle
from ai_trading_shared.domain.enums import (
    NewsCategory,
    RiskLevel,
    SentimentLabel,
    Urgency,
)
from ai_trading_shared.infrastructure.db_models import NewsArticleRow


class InMemoryNewsRepository:
    """Repository for unit tests and offline demos."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, NewsArticle] = {}
        self._hashes: set[str] = set()

    async def upsert(self, article: NewsArticle) -> NewsArticle:
        self._by_id[article.id] = article
        self._hashes.add(article.content_hash)
        return article

    async def exists_by_hash(self, content_hash: str) -> bool:
        return content_hash in self._hashes

    async def get(self, article_id: UUID) -> NewsArticle | None:
        return self._by_id.get(article_id)

    async def list_recent(
        self, limit: int = 50, category: NewsCategory | None = None
    ) -> list[NewsArticle]:
        articles = list(self._by_id.values())
        if category is not None:
            articles = [a for a in articles if a.category == category]
        articles.sort(key=lambda a: a.published_at, reverse=True)
        return articles[:limit]

    async def search(self, query: str, limit: int = 20) -> list[NewsArticle]:
        q = query.lower()
        matches = [
            a
            for a in self._by_id.values()
            if q in a.title.lower() or q in a.body.lower()
        ]
        matches.sort(key=lambda a: a.published_at, reverse=True)
        return matches[:limit]


class SqlAlchemyNewsRepository:
    """PostgreSQL-backed news repository."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def upsert(self, article: NewsArticle) -> NewsArticle:
        async with self._factory() as session:
            existing = await session.scalar(
                select(NewsArticleRow).where(
                    NewsArticleRow.source == article.source,
                    NewsArticleRow.external_id == article.external_id,
                )
            )
            if existing is None:
                row = NewsArticleRow(id=article.id)
                session.add(row)
            else:
                row = existing
            self._apply(row, article)
            await session.commit()
            await session.refresh(row)
            return self._to_entity(row)

    async def exists_by_hash(self, content_hash: str) -> bool:
        async with self._factory() as session:
            row = await session.scalar(
                select(NewsArticleRow.id).where(NewsArticleRow.content_hash == content_hash)
            )
            return row is not None

    async def get(self, article_id: UUID) -> NewsArticle | None:
        async with self._factory() as session:
            row = await session.get(NewsArticleRow, article_id)
            return self._to_entity(row) if row else None

    async def list_recent(
        self, limit: int = 50, category: NewsCategory | None = None
    ) -> list[NewsArticle]:
        async with self._factory() as session:
            stmt = select(NewsArticleRow).order_by(NewsArticleRow.published_at.desc()).limit(limit)
            if category is not None:
                stmt = stmt.where(NewsArticleRow.category == category.value)
            rows = (await session.scalars(stmt)).all()
            return [self._to_entity(r) for r in rows]

    async def search(self, query: str, limit: int = 20) -> list[NewsArticle]:
        async with self._factory() as session:
            pattern = f"%{query}%"
            stmt = (
                select(NewsArticleRow)
                .where(
                    NewsArticleRow.title.ilike(pattern) | NewsArticleRow.body.ilike(pattern)
                )
                .order_by(NewsArticleRow.published_at.desc())
                .limit(limit)
            )
            rows = (await session.scalars(stmt)).all()
            return [self._to_entity(r) for r in rows]

    @staticmethod
    def _apply(row: NewsArticleRow, article: NewsArticle) -> None:
        row.external_id = article.external_id
        row.source = article.source
        row.title = article.title
        row.body = article.body
        row.url = article.url
        row.published_at = article.published_at
        row.ingested_at = article.ingested_at
        row.language = article.language
        row.content_hash = article.content_hash
        row.category = article.category.value
        row.countries = article.countries
        row.sectors = article.sectors
        row.companies = article.companies
        row.industries = article.industries
        row.risk_level = article.risk_level.value
        row.sentiment = article.sentiment.value
        row.sentiment_score = article.sentiment_score
        row.confidence = article.confidence
        row.urgency = article.urgency.value
        row.embedding_id = article.embedding_id

    @staticmethod
    def _to_entity(row: NewsArticleRow) -> NewsArticle:
        return NewsArticle(
            id=row.id,
            external_id=row.external_id,
            source=row.source,
            title=row.title,
            body=row.body,
            url=row.url,
            published_at=row.published_at,
            ingested_at=row.ingested_at,
            language=row.language,
            content_hash=row.content_hash,
            category=NewsCategory(row.category),
            countries=list(row.countries or []),
            sectors=list(row.sectors or []),
            companies=list(row.companies or []),
            industries=list(row.industries or []),
            risk_level=RiskLevel(row.risk_level),
            sentiment=SentimentLabel(row.sentiment),
            sentiment_score=float(row.sentiment_score),
            confidence=float(row.confidence),
            urgency=Urgency(row.urgency),
            embedding_id=row.embedding_id,
        )
