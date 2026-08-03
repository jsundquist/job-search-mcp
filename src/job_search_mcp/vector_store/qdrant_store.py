"""Qdrant implementation of VectorStore.

Default vector store adapter. Works equally against Qdrant Cloud or a
self-hosted Qdrant-in-Docker instance — the choice is a connection detail,
not an interface difference. See docs/adr/0002-vector-store-default-qdrant.md.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import ResponseHandlingException

from job_search_mcp.vector_store.base import VectorRecord

# Qdrant point IDs must be an unsigned integer or a UUID. Our VectorRecord.id
# is a free-form string (per the VectorStore interface), so we map it to a
# deterministic UUID and stash the original id in the payload to round-trip
# it back out in search().
_ID_NAMESPACE = uuid.UUID("a3f5e6c2-9b1a-4d3e-8f2a-1c4b5d6e7f80")
_SOURCE_ID_KEY = "_source_id"


def _point_id(record_id: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, record_id))


class QdrantVectorStore:
    """VectorStore backed by a Qdrant collection (cloud or self-hosted)."""

    def __init__(
        self,
        url: str,
        api_key: str | None,
        collection_name: str,
        vector_size: int,
        distance: qmodels.Distance = qmodels.Distance.COSINE,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        try:
            self._client = QdrantClient(url=url, api_key=api_key)
            self._ensure_collection(vector_size, distance)
        except ResponseHandlingException as exc:
            raise self._connection_error(exc) from exc

    def _connection_error(self, exc: ResponseHandlingException) -> RuntimeError:
        # ResponseHandlingException wraps the underlying httpx/connection error
        # in `.source` but doesn't set its own message, so str(exc) is "" —
        # left unwrapped, callers get an empty, unhelpful error string.
        return RuntimeError(f"Could not reach Qdrant at {self.url}: {exc.source}")

    def _ensure_collection(self, vector_size: int, distance: qmodels.Distance) -> None:
        if self._client.collection_exists(self.collection_name):
            return
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=distance),
        )

    def upsert(self, records: list[VectorRecord]) -> None:
        points = [
            qmodels.PointStruct(
                id=_point_id(record.id),
                vector=record.vector,
                payload={**record.payload, _SOURCE_ID_KEY: record.id},
            )
            for record in records
        ]
        try:
            self._client.upsert(collection_name=self.collection_name, points=points)
        except ResponseHandlingException as exc:
            raise self._connection_error(exc) from exc

    def search(self, query_vector: list[float], top_k: int = 5) -> list[VectorRecord]:
        try:
            results = self._client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                with_vectors=True,
            ).points
        except ResponseHandlingException as exc:
            raise self._connection_error(exc) from exc
        return [_to_vector_record(point) for point in results]

    def delete(self, ids: list[str]) -> None:
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.PointIdsList(points=[_point_id(i) for i in ids]),
            )
        except ResponseHandlingException as exc:
            raise self._connection_error(exc) from exc


def _to_vector_record(point) -> VectorRecord:
    payload = dict(point.payload or {})
    source_id = payload.pop(_SOURCE_ID_KEY, str(point.id))
    return VectorRecord(id=source_id, vector=point.vector or [], payload=payload)
