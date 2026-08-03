"""Resume ingestion: load, chunk, embed, and upsert into a VectorStore.

Standalone module, built against the ResumeSource, Embedder, and
VectorStore interfaces (not against Qdrant or a file format directly) so
the adapter boundaries from Phase 0 are actually exercised.

Resume text is split into light, section/role-sized chunks (see
chunking.py) rather than embedded whole — validation against real job
postings showed whole-document embedding diluted retrieval with
irrelevant resume content, so a JD about one specific area (e.g. AI
tooling) couldn't surface the specific relevant experience on its own.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from job_search_mcp.chunking import chunk_resume_text
from job_search_mcp.embeddings.base import Embedder
from job_search_mcp.resume_source.base import ResumeSource
from job_search_mcp.vector_store.base import VectorRecord, VectorStore


def ingest_resume(
    source: ResumeSource,
    embedder: Embedder,
    vector_store: VectorStore,
    doc_id: str,
) -> None:
    """Load resume content from `source`, chunk it, embed each chunk, and upsert."""
    content = source.get_content()
    chunk_texts = chunk_resume_text(content)
    vectors = embedder.embed_batch(chunk_texts)
    records = [
        VectorRecord(
            id=f"{doc_id}::chunk-{i}",
            vector=vector,
            payload={"text": chunk_text, "resume_id": doc_id, "chunk_index": i},
        )
        for i, (chunk_text, vector) in enumerate(zip(chunk_texts, vectors, strict=True))
    ]
    vector_store.upsert(records)


def _main() -> None:
    from job_search_mcp.config import QdrantConfig
    from job_search_mcp.embeddings.sentence_transformers_embedder import (
        SentenceTransformersEmbedder,
    )
    from job_search_mcp.resume_source.file_source import FileResumeSource
    from job_search_mcp.vector_store.qdrant_store import QdrantVectorStore

    parser = argparse.ArgumentParser(description="Embed a resume file and upsert it into Qdrant.")
    parser.add_argument("resume_path", type=Path, help="Path to a .txt, .md, .pdf, or .docx resume")
    parser.add_argument(
        "--doc-id", default="resume", help="Record id to upsert under (default: 'resume')"
    )
    args = parser.parse_args()

    source = FileResumeSource(args.resume_path)
    embedder = SentenceTransformersEmbedder()
    config = QdrantConfig.from_env()
    vector_store = QdrantVectorStore(
        url=config.url,
        api_key=config.api_key,
        collection_name=config.collection_name,
        vector_size=len(embedder.embed("dimension probe")),
    )

    ingest_resume(source, embedder, vector_store, doc_id=args.doc_id)
    print(f"Ingested {args.resume_path} as chunks of '{args.doc_id}' into '{config.collection_name}'.")


if __name__ == "__main__":
    _main()
