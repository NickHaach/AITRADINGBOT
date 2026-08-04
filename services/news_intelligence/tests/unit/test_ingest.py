"""Unit tests for News Intelligence Engine."""

import pytest

from ai_trading_shared.domain.enums import NewsCategory, RiskLevel, SentimentLabel
from news_intelligence.application.classifier import LexiconNewsClassifier
from news_intelligence.application.ingest import IngestNewsService
from news_intelligence.domain.dedupe import content_hash
from news_intelligence.infrastructure.adapters.mock_feed import MockNewsFeed
from news_intelligence.infrastructure.embeddings.store import InMemoryEmbeddingStore
from news_intelligence.infrastructure.repositories.news_repository import InMemoryNewsRepository


def test_content_hash_stable() -> None:
    a = content_hash("Hello World", "Body text")
    b = content_hash("  hello   world ", "body   text")
    assert a == b


@pytest.mark.asyncio
async def test_classifier_geopolitical_sanctions() -> None:
    clf = LexiconNewsClassifier()
    result = await clf.classify(
        "Breaking: New sanctions package targets Russian energy exports",
        "Western governments announced fresh sanctions on Russia following conflict in Ukraine.",
    )
    assert result["category"] in {NewsCategory.GEOPOLITICAL, NewsCategory.BREAKING, NewsCategory.ENERGY}
    assert result["risk_level"] in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert result["sentiment"] in {
        SentimentLabel.BEARISH,
        SentimentLabel.VERY_BEARISH,
        SentimentLabel.NEUTRAL,
    }
    assert "RU" in result["countries"] or "UA" in result["countries"]
    assert result["confidence"] >= 0.4


@pytest.mark.asyncio
async def test_classifier_nvidia_bullish() -> None:
    clf = LexiconNewsClassifier()
    result = await clf.classify(
        "NVIDIA beats earnings as AI chip demand remains strong",
        "NVIDIA reported record revenue driven by data center AI accelerators.",
    )
    assert result["category"] in {NewsCategory.TECHNOLOGY, NewsCategory.FINANCIAL}
    assert "NVDA" in result["companies"]
    assert result["sentiment_score"] >= 0.0


@pytest.mark.asyncio
async def test_ingest_cycle_deduplicates() -> None:
    service = IngestNewsService(
        feeds=[MockNewsFeed()],
        repository=InMemoryNewsRepository(),
        classifier=LexiconNewsClassifier(),
        embeddings=InMemoryEmbeddingStore(),
    )
    first = await service.run_cycle()
    second = await service.run_cycle()
    assert len(first) >= 5
    assert len(second) == 0  # all duplicates


@pytest.mark.asyncio
async def test_semantic_search_returns_hits() -> None:
    service = IngestNewsService(
        feeds=[MockNewsFeed()],
        repository=InMemoryNewsRepository(),
        classifier=LexiconNewsClassifier(),
        embeddings=InMemoryEmbeddingStore(),
    )
    await service.run_cycle()
    hits = await service.semantic_search("oil OPEC crude energy", limit=5)
    assert len(hits) > 0
    assert "score" in hits[0]
