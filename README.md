# job-search-mcp

An MCP server that ingests a job description, retrieves relevant context
from a resume/experience corpus using RAG, and writes a fit analysis to a
tracking store.

Analysis and tracking only — this project does not generate or tailor
resumes. See `docs/adr/0007-analysis-only-v1-no-resume-generation.md`.

## Design

The server is adapter-based rather than locked to any specific vendor.
Three interfaces define the boundaries:

- **`VectorStore`** (`src/job_search_mcp/vector_store/`) — embedded
  resume/experience chunk storage and similarity search. Default
  implementation: Qdrant (Cloud or self-hosted-in-Docker).
- **`TrackingStore`** (`src/job_search_mcp/tracking_store/`) — persistence
  for fit-analysis results. Default implementation: Notion. A local SQLite
  implementation is the zero-dependency fallback for anyone without Notion.
- **`ResumeSource`** (`src/job_search_mcp/resume_source/`) — retrieval of
  resume/experience content. Default implementation: local text/markdown,
  PDF, and DOCX file parsing. A Google Drive-backed implementation is a
  natural future addition, using the same interface.

Rationale for each of these decisions is recorded in `docs/adr/`.

## Stack

- Python, dependency management via [`uv`](https://docs.astral.sh/uv/)
- [`just`](https://github.com/casey/just) as the task runner (see `justfile`)
- Qdrant (default vector store), Notion (default tracking store)

## Roadmap

Current phase: repo scaffolding and architecture decision records only —
no server or matching code yet.

Planned next:

- Implement the default `VectorStore` (Qdrant), `TrackingStore` (Notion),
  and `ResumeSource` (file-based) adapters
- Implement RAG-based matching logic (`match_job`)
- Wire up the MCP server entrypoint
- Make the Notion tracking field mapping configurable via YAML instead of
  the current v1 hardcoded field list
  (`docs/adr/0004-tracking-field-mapping-v1-shortcut.md`)
- Decide on an embeddings approach (local vs API-based) —
  `docs/adr/0006-embeddings-choice-open.md`
- Local SQLite `TrackingStore` and self-hosted Qdrant-in-Docker
  `VectorStore` implementations for users without Notion/Qdrant Cloud
- Google Drive-backed `ResumeSource` implementation

## Development

```sh
just install   # uv sync
just test      # uv run pytest
just lint      # uv run ruff check .
just run       # no entrypoint yet
```
