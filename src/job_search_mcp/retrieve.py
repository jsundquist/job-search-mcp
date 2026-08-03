"""Retrieval: given a job description, find the most relevant resume content.

Standalone module, built against the Embedder and VectorStore interfaces
so it works against any implementation of either.
"""

from __future__ import annotations

from job_search_mcp.embeddings.base import Embedder
from job_search_mcp.vector_store.base import VectorRecord, VectorStore


def retrieve_relevant_chunks(
    job_description: str,
    embedder: Embedder,
    vector_store: VectorStore,
    top_k: int = 5,
) -> list[VectorRecord]:
    """Embed `job_description` and return the top_k most similar stored records."""
    query_vector = embedder.embed(job_description)
    return vector_store.search(query_vector, top_k=top_k)


def _main() -> None:
    import argparse

    from job_search_mcp.config import QdrantConfig
    from job_search_mcp.embeddings.sentence_transformers_embedder import (
        SentenceTransformersEmbedder,
    )
    from job_search_mcp.vector_store.qdrant_store import QdrantVectorStore

    parser = argparse.ArgumentParser(
        description="Retrieve resume chunks most relevant to a job description."
    )
    parser.add_argument("job_description", help="Job description text")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    embedder = SentenceTransformersEmbedder()
    config = QdrantConfig.from_env()
    vector_store = QdrantVectorStore(
        url=config.url,
        api_key=config.api_key,
        collection_name=config.collection_name,
        vector_size=len(embedder.embed("dimension probe")),
    )

    results = retrieve_relevant_chunks(args.job_description, embedder, vector_store, args.top_k)
    for record in results:
        print(f"--- {record.id} ---")
        print(record.payload.get("text", ""))
        print()


if __name__ == "__main__":
    _main()
