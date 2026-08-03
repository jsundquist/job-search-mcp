"""MCP server exposing job-search-mcp's retrieval tools.

Run with: uv run job-search-mcp
Or registered with Claude Code — see README.
"""

from __future__ import annotations

from mcp.server import MCPServer

from job_search_mcp.config import QdrantConfig
from job_search_mcp.embeddings.base import Embedder
from job_search_mcp.embeddings.sentence_transformers_embedder import SentenceTransformersEmbedder
from job_search_mcp.match_job import FitAnalysis, build_fit_analysis
from job_search_mcp.vector_store.base import VectorStore
from job_search_mcp.vector_store.qdrant_store import QdrantVectorStore

mcp = MCPServer("job-search-mcp")

_embedder: Embedder | None = None
_vector_store: VectorStore | None = None


def _get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformersEmbedder()
    return _embedder


def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        config = QdrantConfig.from_env()
        _vector_store = QdrantVectorStore(
            url=config.url,
            api_key=config.api_key,
            collection_name=config.collection_name,
            vector_size=len(_get_embedder().embed("dimension probe")),
        )
    return _vector_store


@mcp.tool()
def match_job(job_description: str, source_url: str | None = None) -> FitAnalysis:
    """Retrieve resume/experience evidence relevant to a job description.

    Args:
        job_description: The full text of the job description to match against.
        source_url: Optional URL the job description was pulled from, for reference.

    Returns a heuristic fit_score (top-match cosine similarity) and the
    retrieved resume chunks with their individual similarity scores. Does
    not synthesize strengths/gaps/notes — reason over the retrieved
    evidence yourself.
    """
    return build_fit_analysis(job_description, source_url, _get_embedder(), _get_vector_store())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
