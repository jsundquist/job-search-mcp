"""match_job: retrieve resume evidence relevant to a job description.

No internal LLM call — this returns retrieved evidence and a heuristic
similarity-based score, not a synthesized strengths/gaps writeup. The
calling assistant is expected to reason over the returned evidence.
"""

from __future__ import annotations

from typing import TypedDict

from job_search_mcp.embeddings.base import Embedder
from job_search_mcp.retrieve import retrieve_relevant_chunks
from job_search_mcp.similarity import cosine_similarity
from job_search_mcp.vector_store.base import VectorStore


class RetrievedChunk(TypedDict):
    chunk_id: str
    text: str
    similarity: float


class FitAnalysis(TypedDict):
    job_description: str
    source_url: str | None
    fit_score: float
    retrieved_chunks: list[RetrievedChunk]


def build_fit_analysis(
    job_description: str,
    source_url: str | None,
    embedder: Embedder,
    vector_store: VectorStore,
    top_k: int = 5,
) -> FitAnalysis:
    query_vector = embedder.embed(job_description)
    records = retrieve_relevant_chunks(job_description, embedder, vector_store, top_k=top_k)

    retrieved_chunks: list[RetrievedChunk] = sorted(
        (
            {
                "chunk_id": record.id,
                "text": record.payload.get("text", ""),
                "similarity": cosine_similarity(query_vector, record.vector),
            }
            for record in records
        ),
        key=lambda chunk: chunk["similarity"],
        reverse=True,
    )
    fit_score = retrieved_chunks[0]["similarity"] if retrieved_chunks else 0.0

    return {
        "job_description": job_description,
        "source_url": source_url,
        "fit_score": fit_score,
        "retrieved_chunks": retrieved_chunks,
    }
