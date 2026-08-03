"""Connection-failure handling for QdrantVectorStore.

Unit-level (no real Qdrant needed) — monkeypatches the client to simulate
what qdrant_client actually raises when the server is unreachable:
ResponseHandlingException, which carries no message of its own (str(exc)
is "") unless wrapped.
"""

from __future__ import annotations

import pytest
from qdrant_client.http.exceptions import ResponseHandlingException

from job_search_mcp.vector_store.qdrant_store import QdrantVectorStore


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def collection_exists(self, collection_name):
        raise ResponseHandlingException(ConnectionError("Connection refused"))

    def query_points(self, **kwargs):
        raise ResponseHandlingException(ConnectionError("Connection refused"))


def _make_store(monkeypatch) -> QdrantVectorStore:
    monkeypatch.setattr("job_search_mcp.vector_store.qdrant_store.QdrantClient", _FakeClient)
    return QdrantVectorStore(
        url="http://localhost:9999",
        api_key=None,
        collection_name="test",
        vector_size=4,
    )


def test_unreachable_qdrant_raises_informative_error_on_construction(monkeypatch):
    with pytest.raises(RuntimeError, match="Could not reach Qdrant at http://localhost:9999"):
        _make_store(monkeypatch)


def test_unreachable_qdrant_raises_informative_error_on_search(monkeypatch):
    monkeypatch.setattr("job_search_mcp.vector_store.qdrant_store.QdrantClient", _FakeClient)
    store = QdrantVectorStore.__new__(QdrantVectorStore)
    store.url = "http://localhost:9999"
    store.collection_name = "test"
    store._client = _FakeClient()

    with pytest.raises(RuntimeError, match="Could not reach Qdrant at http://localhost:9999"):
        store.search([0.1, 0.2, 0.3, 0.4])
