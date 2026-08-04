"""News domain ports (interfaces)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from pydantic import Field

from ai_trading_shared.domain.entities import NewsArticle
from ai_trading_shared.domain.enums import DomainModel, NewsCategory, RiskLevel, SentimentLabel, Urgency


class RawNewsItem(DomainModel):
    """Normalized raw item from any feed adapter before enrichment."""

    external_id: str
    source: str
    title: str
    body: str
    url: Optional[str] = None
    published_at: datetime
    language: str = "en"
    raw_metadata: dict = Field(default_factory=dict)


class NewsFeedPort(Protocol):
    """Port for external news sources."""

    name: str

    async def fetch_since(self, since: datetime | None = None, limit: int = 50) -> list[RawNewsItem]:
        ...


class NewsRepositoryPort(Protocol):
    async def upsert(self, article: NewsArticle) -> NewsArticle:
        ...

    async def exists_by_hash(self, content_hash: str) -> bool:
        ...

    async def get(self, article_id: UUID) -> NewsArticle | None:
        ...

    async def list_recent(self, limit: int = 50, category: NewsCategory | None = None) -> list[NewsArticle]:
        ...

    async def search(self, query: str, limit: int = 20) -> list[NewsArticle]:
        ...


class EmbeddingPort(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    async def upsert_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        ...

    async def search(self, vector: list[float], limit: int = 10) -> list[dict]:
        ...


class ClassifierPort(Protocol):
    async def classify(self, title: str, body: str) -> dict:
        """Return classification fields for an article."""
        ...
