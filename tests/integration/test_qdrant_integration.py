"""Integration test against a real Qdrant instance (Cloud or self-hosted).

Skipped automatically unless QDRANT_URL is set (see .env.example) — the
unit tests in tests/unit/ do not require a live connection. Run explicitly
with: uv run pytest -m integration

Uses its own dedicated, disposable collection so it never touches the
collection configured for real ingestion via QDRANT_COLLECTION_NAME.
"""

from __future__ import annotations

import os
import uuid

import pytest

from job_search_mcp.embeddings.sentence_transformers_embedder import SentenceTransformersEmbedder
from job_search_mcp.ingest import ingest_resume
from job_search_mcp.resume_source.file_source import FileResumeSource
from job_search_mcp.retrieve import retrieve_relevant_chunks
from job_search_mcp.vector_store.qdrant_store import QdrantVectorStore

pytestmark = pytest.mark.integration

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "resumes")


@pytest.mark.skipif(not os.environ.get("QDRANT_URL"), reason="QDRANT_URL not set")
def test_ingest_and_retrieve_against_real_qdrant():
    embedder = SentenceTransformersEmbedder()
    collection_name = f"job_search_mcp_test_{uuid.uuid4().hex[:8]}"
    store = QdrantVectorStore(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ.get("QDRANT_API_KEY") or None,
        collection_name=collection_name,
        vector_size=len(embedder.embed("dimension probe")),
    )

    try:
        source = FileResumeSource(os.path.join(FIXTURES_DIR, "sample_resume.txt"))
        ingest_resume(source, embedder, store, doc_id="resume")

        results = retrieve_relevant_chunks(
            "Senior Software Engineer with Python and cloud experience",
            embedder,
            store,
            top_k=1,
        )

        assert len(results) == 1
        assert results[0].id == "resume"
        assert "Jane Example" in results[0].payload["text"]
    finally:
        store._client.delete_collection(collection_name)
