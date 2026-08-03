"""Qdrant implementation of VectorStore.

Default vector store adapter. Works equally against Qdrant Cloud or a
self-hosted Qdrant-in-Docker instance — the choice is a connection detail,
not an interface difference. See docs/adr/0002-vector-store-default-qdrant.md.

Not yet implemented — scaffolding only.
"""

from __future__ import annotations

from job_search_mcp.vector_store.base import VectorRecord


class QdrantVectorStore:
    """VectorStore backed by a Qdrant collection (cloud or self-hosted)."""

    def __init__(self, url: str, api_key: str | None, collection_name: str) -> None:
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name

    def upsert(self, records: list[VectorRecord]) -> None:
        raise NotImplementedError

    def search(self, query_vector: list[float], top_k: int = 5) -> list[VectorRecord]:
        raise NotImplementedError

    def delete(self, ids: list[str]) -> None:
        raise NotImplementedError
