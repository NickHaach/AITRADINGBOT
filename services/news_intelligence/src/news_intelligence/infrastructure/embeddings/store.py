"""Embedding adapters: deterministic hash vectors (default) and Qdrant store."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from ai_trading_shared.utils.logging import get_logger

logger = get_logger(__name__)


def hash_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic pseudo-embedding from text (no model download required).

    Suitable for tests and local bootstrapping. Swap for SentenceTransformers
    or OpenAI embeddings in production via EmbeddingPort.
    """
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim).astype(np.float64)
    for token in set(text.lower().split()):
        token_seed = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)  # noqa: S324
        idx = token_seed % dim
        vec[idx] += 1.0
    norm = float(np.linalg.norm(vec) or 1.0)
    return (vec / norm).tolist()


class InMemoryEmbeddingStore:
    """Local vector store used when Qdrant is unavailable."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim
        self._vectors: dict[str, list[float]] = {}
        self._payloads: dict[str, dict[str, Any]] = {}

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [hash_embed(t, self.dim) for t in texts]

    async def upsert_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        for i, vec, payload in zip(ids, vectors, payloads):
            self._vectors[i] = vec
            self._payloads[i] = payload

    async def search(self, vector: list[float], limit: int = 10) -> list[dict]:
        scored: list[tuple[float, str]] = []
        q = np.array(vector)
        for vid, stored in self._vectors.items():
            s = np.array(stored)
            score = float(np.dot(q, s) / ((np.linalg.norm(q) * np.linalg.norm(s)) or 1.0))
            scored.append((score, vid))
        scored.sort(reverse=True)
        results: list[dict] = []
        for score, vid in scored[:limit]:
            results.append(
                {"id": vid, "score": score, "payload": self._payloads.get(vid, {})}
            )
        return results


class QdrantEmbeddingStore:
    """Qdrant-backed embedding store with hash embed fallback encoder."""

    def __init__(
        self,
        url: str,
        collection: str,
        api_key: str | None = None,
        dim: int = 384,
    ) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qmodels

        self.dim = dim
        self.collection = collection
        self._qmodels = qmodels
        self._client = QdrantClient(url=url, api_key=api_key or None)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        names = [c.name for c in self._client.get_collections().collections]
        if self.collection not in names:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=self._qmodels.VectorParams(
                    size=self.dim,
                    distance=self._qmodels.Distance.COSINE,
                ),
            )
            logger.info("qdrant_collection_created", collection=self.collection)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [hash_embed(t, self.dim) for t in texts]

    async def upsert_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        points = [
            self._qmodels.PointStruct(id=i, vector=v, payload=p)
            for i, v, p in zip(ids, vectors, payloads)
        ]
        self._client.upsert(collection_name=self.collection, points=points)

    async def search(self, vector: list[float], limit: int = 10) -> list[dict]:
        hits = self._client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=limit,
        )
        return [
            {"id": str(h.id), "score": float(h.score), "payload": h.payload or {}}
            for h in hits
        ]
