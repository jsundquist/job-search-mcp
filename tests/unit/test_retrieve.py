from job_search_mcp.retrieve import retrieve_relevant_chunks
from job_search_mcp.vector_store.base import VectorRecord
from job_search_mcp.vector_store.in_memory_store import InMemoryVectorStore


class _StubEmbedder:
    """Returns a fixed vector for any input, so the test controls ranking directly."""

    def __init__(self, vector):
        self._vector = vector

    def embed(self, text):
        return self._vector

    def embed_batch(self, texts):
        return [self._vector for _ in texts]


def test_retrieve_relevant_chunks_returns_closest_match():
    store = InMemoryVectorStore()
    store.upsert(
        [
            VectorRecord(id="close", vector=[1.0, 0.0], payload={"text": "close"}),
            VectorRecord(id="far", vector=[0.0, 1.0], payload={"text": "far"}),
        ]
    )
    embedder = _StubEmbedder(vector=[1.0, 0.0])

    results = retrieve_relevant_chunks("some job description", embedder, store, top_k=1)

    assert len(results) == 1
    assert results[0].id == "close"


def test_retrieve_relevant_chunks_respects_top_k():
    store = InMemoryVectorStore()
    store.upsert([VectorRecord(id=str(i), vector=[float(i), 0.0]) for i in range(5)])
    embedder = _StubEmbedder(vector=[1.0, 0.0])

    results = retrieve_relevant_chunks("query", embedder, store, top_k=3)

    assert len(results) == 3
