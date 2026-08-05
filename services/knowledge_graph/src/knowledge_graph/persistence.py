"""SQL-backed knowledge graph persistence."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_shared.infrastructure.db_models import GraphEdgeRow, GraphNodeRow
from knowledge_graph.engine import GraphEdge, GraphNode, KnowledgeGraph


class SqlKnowledgeGraphStore:
    """Load/save KnowledgeGraph snapshots to Postgres/SQLite graph tables."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def persist(self, graph: KnowledgeGraph) -> Dict[str, int]:
        async with self._factory() as session:
            # upsert nodes
            for node in graph._nodes.values():
                existing = await session.scalar(
                    select(GraphNodeRow).where(
                        GraphNodeRow.node_type == node.node_type,
                        GraphNodeRow.external_key == node.external_key,
                    )
                )
                if existing is None:
                    session.add(
                        GraphNodeRow(
                            id=node.id,
                            node_type=node.node_type,
                            external_key=node.external_key,
                            label=node.label,
                            properties=node.properties,
                        )
                    )
                else:
                    existing.label = node.label
                    existing.properties = node.properties

            # naive edge replace for this process snapshot: insert missing
            existing_edge_keys = set()
            for row in (await session.scalars(select(GraphEdgeRow))).all():
                existing_edge_keys.add((str(row.from_node_id), str(row.to_node_id), row.relationship))

            inserted = 0
            for edge in graph._edges:
                key = (str(edge.from_node_id), str(edge.to_node_id), edge.relationship)
                if key in existing_edge_keys:
                    continue
                session.add(
                    GraphEdgeRow(
                        id=edge.id,
                        from_node_id=edge.from_node_id,
                        to_node_id=edge.to_node_id,
                        relationship=edge.relationship,
                        weight=edge.weight,
                        properties=edge.properties,
                    )
                )
                inserted += 1
            await session.commit()
            return {"nodes": len(graph._nodes), "edges_inserted": inserted}

    async def load(self) -> KnowledgeGraph:
        graph = KnowledgeGraph()
        async with self._factory() as session:
            nodes = (await session.scalars(select(GraphNodeRow))).all()
            id_map: Dict[UUID, GraphNode] = {}
            for row in nodes:
                node = GraphNode(
                    id=row.id,
                    node_type=row.node_type,
                    external_key=row.external_key,
                    label=row.label,
                    properties=row.properties or {},
                )
                graph._nodes[node.id] = node
                graph._by_key[(node.node_type, node.external_key)] = node.id
                id_map[row.id] = node

            edges = (await session.scalars(select(GraphEdgeRow))).all()
            for row in edges:
                if row.from_node_id not in id_map or row.to_node_id not in id_map:
                    continue
                graph._edges.append(
                    GraphEdge(
                        id=row.id,
                        from_node_id=row.from_node_id,
                        to_node_id=row.to_node_id,
                        relationship=row.relationship,
                        weight=float(row.weight),
                        properties=row.properties or {},
                    )
                )
        return graph
