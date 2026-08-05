"""Knowledge graph SQL persistence tests (SQLite)."""

from __future__ import annotations

import pytest

from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
from ai_trading_shared.infrastructure.db_models import GraphEdgeRow, GraphNodeRow
from knowledge_graph.engine import KnowledgeGraph
from knowledge_graph.persistence import SqlKnowledgeGraphStore


@pytest.fixture
async def store(tmp_path):
    db_path = tmp_path / "graph.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: GraphNodeRow.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: GraphEdgeRow.__table__.create(c, checkfirst=True))
    factory = create_session_factory(engine)
    yield SqlKnowledgeGraphStore(factory)
    await engine.dispose()


@pytest.mark.asyncio
async def test_graph_persist_and_load(store: SqlKnowledgeGraphStore) -> None:
    g = KnowledgeGraph()
    g.ingest_news(
        article_id="n1",
        title="NVIDIA AI demand surges",
        tickers=["NVDA", "MSFT"],
        sectors=["Technology"],
        countries=["US"],
        sentiment_score=0.6,
    )
    result = await store.persist(g)
    assert result["nodes"] >= 3
    assert result["edges_inserted"] >= 1

    loaded = await store.load()
    assert loaded.stats()["nodes"] >= 3
    related = loaded.related_tickers("NVDA")
    assert any(r["ticker"] == "MSFT" for r in related)
