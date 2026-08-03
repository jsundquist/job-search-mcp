"""MCP server exposing job-search-mcp's retrieval tools.

Run with: uv run job-search-mcp
Or registered with Claude Code — see README.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server import MCPServer
from mcp_types import CallToolResult, ResourceLink, TextContent

from job_search_mcp.config import NotionConfig, QdrantConfig, tracking_schema_path_from_env
from job_search_mcp.embeddings.base import Embedder
from job_search_mcp.embeddings.sentence_transformers_embedder import SentenceTransformersEmbedder
from job_search_mcp.fit_verdict import FitVerdict
from job_search_mcp.match_job import FitAnalysis, build_fit_analysis
from job_search_mcp.tracking_store.base import TrackingStore
from job_search_mcp.tracking_store.mapping import build_notion_properties_from_schema
from job_search_mcp.tracking_store.notion_store import NotionTrackingStore
from job_search_mcp.tracking_store.schema import TrackingSchema, load_tracking_schema
from job_search_mcp.vector_store.base import VectorStore
from job_search_mcp.vector_store.qdrant_store import QdrantVectorStore

mcp = MCPServer("job-search-mcp")

JOB_FIT_RUBRIC_URI = "job-fit://rubric"
_JOB_FIT_RUBRIC_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "job_fit_scoring_algorithm.md"

_embedder: Embedder | None = None
_vector_store: VectorStore | None = None
_tracking_store: TrackingStore | None = None
_tracking_schema: TrackingSchema | None = None


def _get_tracking_schema() -> TrackingSchema:
    global _tracking_schema
    if _tracking_schema is None:
        _tracking_schema = load_tracking_schema(tracking_schema_path_from_env())
    return _tracking_schema


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


def _get_tracking_store() -> TrackingStore:
    global _tracking_store
    if _tracking_store is None:
        config = NotionConfig.from_env()
        _tracking_store = NotionTrackingStore(
            database_id=config.database_id, api_key=config.api_key, schema=_get_tracking_schema()
        )
    return _tracking_store


@mcp.resource(
    JOB_FIT_RUBRIC_URI,
    name="job-fit-rubric",
    title="Job fit scoring algorithm",
    description=(
        "5-layer rubric (hard gates, domain match, scope match, preference/logistics, "
        "red flags) for turning match_job's retrieved evidence into a fit bucket. "
        "retrieval_score alone is not a reliable fit signal — apply this instead."
    ),
    mime_type="text/markdown",
)
def job_fit_rubric() -> str:
    return _JOB_FIT_RUBRIC_PATH.read_text(encoding="utf-8")


@mcp.tool()
def match_job(job_description: str, source_url: str | None = None) -> FitAnalysis:
    """Retrieve resume/experience evidence relevant to a job description.

    Args:
        job_description: The full text of the job description to match against.
        source_url: Optional URL the job description was pulled from, for reference.

    Returns a heuristic retrieval_score (top-match cosine similarity) and the
    retrieved resume chunks with their individual similarity scores. Does
    not synthesize strengths/gaps/notes — reason over the retrieved
    evidence yourself, applying the job-fit://rubric resource linked in this
    result.
    """
    if not job_description or not job_description.strip():
        raise ValueError("job_description must not be empty.")

    analysis = build_fit_analysis(job_description, source_url, _get_embedder(), _get_vector_store())
    content = [
        TextContent(type="text", text=json.dumps(analysis, indent=2)),
        ResourceLink(
            type="resource_link",
            uri=JOB_FIT_RUBRIC_URI,
            name="job-fit-rubric",
            title="Job fit scoring algorithm",
            mime_type="text/markdown",
            description="Apply this rubric to the retrieved evidence above to determine a fit bucket.",
        ),
    ]
    return CallToolResult(content=content, structured_content=analysis)


@mcp.tool()
def push_to_tracker(job_id: str, verdict: FitVerdict, dry_run: bool = False) -> dict:
    """Write an evaluate_fit result to the configured tracking store (Notion).

    Args:
        job_id: The Notion page ID of the job you already track. Updates
            that existing row in place — never creates a new row.
        verdict: The full evaluate_fit output (see docs/evaluate_fit_schema.md).
        dry_run: If true, returns the mapped Notion properties payload
            without writing anything, so you can review it first.

    Only the fields your tracking_schema.yaml marks tool-populated are
    touched — every other, manual field on the row (company, comp range,
    source, work arrangement, etc.) is left as-is. See
    docs/adr/0011-configurable-tracking-field-schema.md.

    A misconfigured tool-populated field (an unrecognized derived_from,
    or — on a real write, not dry_run — a notion.property that doesn't
    exist on your database) is skipped rather than failing the whole
    write; check `warnings` in the result. dry_run's warnings only cover
    what can be checked without a Notion API call, since dry_run makes
    none — a bad property name only shows up in `warnings` on a real write.
    """
    if not job_id or not job_id.strip():
        raise ValueError("job_id must not be empty.")

    properties, preview_warnings = build_notion_properties_from_schema(_get_tracking_schema(), verdict)
    if dry_run:
        return {"job_id": job_id, "dry_run": True, "properties": properties, "warnings": preview_warnings}

    write_warnings = _get_tracking_store().record_analysis(job_id, verdict)
    return {"job_id": job_id, "dry_run": False, "properties": properties, "warnings": write_warnings}


@mcp.tool()
def list_applications(status: str | None = None) -> list[dict]:
    """List tracked jobs from the configured tracking store (Notion).

    Args:
        status: If given, only return rows whose Status matches exactly
            (e.g. "Not yet applied", "Applied"). Case-sensitive — must
            match the tracking store's status value exactly. Omit to
            return every tracked row.

    Each entry has job_id plus whatever tool-populated fields your
    tracking_schema.yaml declares (see
    docs/adr/0011-configurable-tracking-field-schema.md) — typically
    status, fit_rating, and notes. Statuses beyond "Not yet applied"
    (Applied, Recruiter screen, ...) are manual edits made in Notion, not
    something this server drives.
    """
    analyses = _get_tracking_store().list_analyses()
    if status is None:
        return analyses
    return [a for a in analyses if a.get("status") == status]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
