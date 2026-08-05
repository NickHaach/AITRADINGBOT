"""Knowledge Graph — link news, filings, tickers, sectors, and geo events."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from ai_trading_shared.config import get_settings
from ai_trading_shared.domain.enums import DomainModel, new_id

__version__ = "0.1.0"


class GraphNode(DomainModel):
    id: UUID = Field(default_factory=new_id)
    node_type: str
    external_key: str
    label: str
    properties: Dict = Field(default_factory=dict)


class GraphEdge(DomainModel):
    id: UUID = Field(default_factory=new_id)
    from_node_id: UUID
    to_node_id: UUID
    relationship: str
    weight: float = 1.0
    properties: Dict = Field(default_factory=dict)


class KnowledgeGraph:
    """In-memory graph with optional SQL sync later.

    Node types: ticker | news | filing | sector | country | geo_event
    Relationships: MENTIONS | ABOUT | IN_SECTOR | IN_COUNTRY | IMPACTS | RELATED_TO
    """

    def __init__(self) -> None:
        self._nodes: Dict[UUID, GraphNode] = {}
        self._by_key: Dict[Tuple[str, str], UUID] = {}
        self._edges: List[GraphEdge] = []

    def upsert_node(
        self,
        node_type: str,
        external_key: str,
        label: str,
        properties: Optional[Dict] = None,
    ) -> GraphNode:
        key = (node_type, external_key)
        existing_id = self._by_key.get(key)
        if existing_id:
            node = self._nodes[existing_id]
            node.label = label
            if properties:
                node.properties.update(properties)
            return node
        node = GraphNode(
            node_type=node_type,
            external_key=external_key,
            label=label,
            properties=properties or {},
        )
        self._nodes[node.id] = node
        self._by_key[key] = node.id
        return node

    def link(
        self,
        from_node: GraphNode,
        to_node: GraphNode,
        relationship: str,
        weight: float = 1.0,
        properties: Optional[Dict] = None,
    ) -> GraphEdge:
        for edge in self._edges:
            if (
                edge.from_node_id == from_node.id
                and edge.to_node_id == to_node.id
                and edge.relationship == relationship
            ):
                edge.weight = weight
                if properties:
                    edge.properties.update(properties)
                return edge
        edge = GraphEdge(
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            relationship=relationship,
            weight=weight,
            properties=properties or {},
        )
        self._edges.append(edge)
        return edge

    def ingest_news(
        self,
        *,
        article_id: str,
        title: str,
        tickers: List[str],
        sectors: List[str],
        countries: List[str],
        sentiment_score: float = 0.0,
    ) -> GraphNode:
        news = self.upsert_node(
            "news",
            article_id,
            title,
            {"sentiment_score": sentiment_score},
        )
        for ticker in tickers:
            t = self.upsert_node("ticker", ticker.upper(), ticker.upper())
            self.link(news, t, "MENTIONS", weight=1.0 + abs(sentiment_score))
        for sector in sectors:
            s = self.upsert_node("sector", sector, sector)
            self.link(news, s, "ABOUT", weight=0.8)
        for country in countries:
            c = self.upsert_node("country", country.upper(), country.upper())
            self.link(news, c, "IN_COUNTRY", weight=0.7)
        return news

    def ingest_filing(
        self,
        *,
        filing_id: str,
        title: str,
        ticker: str,
        filing_type: str,
        impact_score: float = 0.0,
    ) -> GraphNode:
        filing = self.upsert_node(
            "filing",
            filing_id,
            title,
            {"filing_type": filing_type, "impact_score": impact_score},
        )
        t = self.upsert_node("ticker", ticker.upper(), ticker.upper())
        self.link(filing, t, "ABOUT", weight=1.0 + abs(impact_score))
        return filing

    def ingest_geo_event(
        self,
        *,
        event_id: str,
        title: str,
        countries: List[str],
        channels: Dict[str, float],
    ) -> GraphNode:
        event = self.upsert_node("geo_event", event_id, title, {"channels": channels})
        for country in countries:
            c = self.upsert_node("country", country.upper(), country.upper())
            self.link(event, c, "IN_COUNTRY", weight=1.0)
        # Map impact channels to sector/ticker proxies
        channel_to_ticker = {
            "oil": "XOM",
            "gold": "GLD",
            "defense": "LMT",
            "semiconductors": "NVDA",
            "shipping": "FDX",
        }
        for channel, impact in channels.items():
            ticker = channel_to_ticker.get(channel)
            if not ticker:
                continue
            t = self.upsert_node("ticker", ticker, ticker)
            self.link(event, t, "IMPACTS", weight=abs(float(impact)), properties={"channel": channel})
        return event

    def neighbors(
        self,
        node_type: str,
        external_key: str,
        relationship: Optional[str] = None,
    ) -> List[Dict]:
        node_id = self._by_key.get((node_type, external_key))
        if node_id is None:
            return []
        results: List[Dict] = []
        for edge in self._edges:
            if edge.from_node_id != node_id and edge.to_node_id != node_id:
                continue
            if relationship and edge.relationship != relationship:
                continue
            other_id = edge.to_node_id if edge.from_node_id == node_id else edge.from_node_id
            other = self._nodes[other_id]
            results.append(
                {
                    "relationship": edge.relationship,
                    "weight": edge.weight,
                    "node": other.model_dump(mode="json"),
                    "direction": "out" if edge.from_node_id == node_id else "in",
                }
            )
        results.sort(key=lambda r: r["weight"], reverse=True)
        return results

    def related_tickers(self, seed_ticker: str, limit: int = 10) -> List[Dict]:
        """Find tickers co-mentioned via shared news/filings/geo events."""
        seed_id = self._by_key.get(("ticker", seed_ticker.upper()))
        if seed_id is None:
            return []
        # gather intermediary nodes connected to seed
        mids: Set[UUID] = set()
        for edge in self._edges:
            if edge.from_node_id == seed_id:
                mids.add(edge.to_node_id)
            elif edge.to_node_id == seed_id:
                mids.add(edge.from_node_id)
        scores: Dict[str, float] = {}
        for edge in self._edges:
            other: Optional[GraphNode] = None
            if edge.from_node_id in mids:
                other = self._nodes.get(edge.to_node_id)
            elif edge.to_node_id in mids:
                other = self._nodes.get(edge.from_node_id)
            if other is None or other.node_type != "ticker":
                continue
            if other.external_key == seed_ticker.upper():
                continue
            scores[other.external_key] = scores.get(other.external_key, 0.0) + float(edge.weight)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [{"ticker": t, "score": round(s, 4)} for t, s in ranked]

    def stats(self) -> Dict[str, int]:
        by_type: Dict[str, int] = {}
        for node in self._nodes.values():
            by_type[node.node_type] = by_type.get(node.node_type, 0) + 1
        return {"nodes": len(self._nodes), "edges": len(self._edges), **by_type}


graph = KnowledgeGraph()
app = FastAPI(title="Knowledge Graph", version=__version__)


class NewsIngestRequest(BaseModel):
    article_id: str
    title: str
    tickers: List[str] = Field(default_factory=list)
    sectors: List[str] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    sentiment_score: float = 0.0


class FilingIngestRequest(BaseModel):
    filing_id: str
    title: str
    ticker: str
    filing_type: str
    impact_score: float = 0.0


class GeoIngestRequest(BaseModel):
    event_id: str
    title: str
    countries: List[str] = Field(default_factory=list)
    channels: Dict[str, float] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "knowledge_graph", **graph.stats()}


@app.post("/v1/graph/news")
async def ingest_news(body: NewsIngestRequest) -> dict:
    node = graph.ingest_news(**body.model_dump())
    return node.model_dump(mode="json")


@app.post("/v1/graph/filings")
async def ingest_filing(body: FilingIngestRequest) -> dict:
    node = graph.ingest_filing(**body.model_dump())
    return node.model_dump(mode="json")


@app.post("/v1/graph/geo")
async def ingest_geo(body: GeoIngestRequest) -> dict:
    node = graph.ingest_geo_event(**body.model_dump())
    return node.model_dump(mode="json")


@app.get("/v1/graph/neighbors")
async def neighbors(
    node_type: str,
    key: str,
    relationship: Optional[str] = None,
) -> List[dict]:
    return graph.neighbors(node_type, key, relationship)


@app.get("/v1/graph/related-tickers")
async def related_tickers(ticker: str, limit: int = Query(10, ge=1, le=50)) -> List[dict]:
    return graph.related_tickers(ticker, limit=limit)


@app.get("/v1/graph/stats")
async def stats() -> dict:
    return graph.stats()


@app.post("/v1/graph/persist")
async def persist_graph() -> dict:
    """Persist in-memory graph to SQL when ENABLE_SQL_PERSISTENCE=true."""
    settings = get_settings()
    if not settings.enable_sql_persistence:
        return {"persisted": False, "reason": "enable_sql_persistence_required"}
    if not settings.database_url.startswith("postgresql"):
        return {"persisted": False, "reason": "sql_persist_requires_postgres"}
    from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
    from knowledge_graph.persistence import SqlKnowledgeGraphStore

    engine = create_engine(settings.database_url)
    store = SqlKnowledgeGraphStore(create_session_factory(engine))
    result = await store.persist(graph)
    return {"persisted": True, **result}


@app.post("/v1/graph/load")
async def load_graph() -> dict:
    settings = get_settings()
    if not settings.enable_sql_persistence:
        return {"loaded": False, "reason": "enable_sql_persistence_required"}
    if not settings.database_url.startswith("postgresql"):
        return {"loaded": False, "reason": "sql_load_requires_postgres"}
    from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
    from knowledge_graph.persistence import SqlKnowledgeGraphStore

    global graph
    engine = create_engine(settings.database_url)
    store = SqlKnowledgeGraphStore(create_session_factory(engine))
    graph = await store.load()
    return {"loaded": True, **graph.stats()}
