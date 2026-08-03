"""In-memory implementation of VectorStore.

Zero-dependency fallback: no external service required. Useful for tests
and local experimentation without a Qdrant connection. Similarity search
uses plain cosine similarity over a Python list — fine at small scale, not
intended to replace a real vector database at scale.
"""

from __future__ import annotations

import math

from job_search_mcp.vector_store.base import VectorRecord


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    """VectorStore backed by an in-process dict — no external service."""

    def __init__(self) -> None:
        self._records: dict[str, VectorRecord] = {}

    def upsert(self, records: list[VectorRecord]) -> None:
        for record in records:
            self._records[record.id] = record

    def search(self, query_vector: list[float], top_k: int = 5) -> list[VectorRecord]:
        scored = sorted(
            self._records.values(),
            key=lambda r: _cosine_similarity(r.vector, query_vector),
            reverse=True,
        )
        return scored[:top_k]

    def delete(self, ids: list[str]) -> None:
        for record_id in ids:
            self._records.pop(record_id, None)
