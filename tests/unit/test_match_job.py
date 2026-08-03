from job_search_mcp.match_job import build_fit_analysis
from job_search_mcp.vector_store.base import VectorRecord
from job_search_mcp.vector_store.in_memory_store import InMemoryVectorStore


class _StubEmbedder:
    """Returns a fixed vector for any input, so the test controls similarity directly."""

    def __init__(self, vector):
        self._vector = vector

    def embed(self, text):
        return self._vector

    def embed_batch(self, texts):
        return [self._vector for _ in texts]


def test_build_fit_analysis_returns_evidence_and_score():
    store = InMemoryVectorStore()
    store.upsert(
        [
            VectorRecord(id="resume", vector=[1.0, 0.0], payload={"text": "Python, Go, AWS"}),
        ]
    )
    embedder = _StubEmbedder(vector=[1.0, 0.0])

    result = build_fit_analysis("Senior backend engineer", "https://example.com/job", embedder, store)

    assert result["job_description"] == "Senior backend engineer"
    assert result["source_url"] == "https://example.com/job"
    assert result["retrieval_score"] == 1.0
    assert result["retrieved_chunks"] == [
        {"chunk_id": "resume", "text": "Python, Go, AWS", "similarity": 1.0}
    ]


def test_build_fit_analysis_chunks_sorted_by_similarity_descending():
    store = InMemoryVectorStore()
    store.upsert(
        [
            VectorRecord(id="far", vector=[0.0, 1.0], payload={"text": "far"}),
            VectorRecord(id="close", vector=[1.0, 0.0], payload={"text": "close"}),
        ]
    )
    embedder = _StubEmbedder(vector=[1.0, 0.0])

    result = build_fit_analysis("job description", None, embedder, store)

    assert [c["chunk_id"] for c in result["retrieved_chunks"]] == ["close", "far"]
    assert result["retrieval_score"] == result["retrieved_chunks"][0]["similarity"]


def test_build_fit_analysis_no_matches_returns_zero_score():
    store = InMemoryVectorStore()
    embedder = _StubEmbedder(vector=[1.0, 0.0])

    result = build_fit_analysis("job description", None, embedder, store)

    assert result["retrieval_score"] == 0.0
    assert result["retrieved_chunks"] == []
