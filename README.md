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

Embeddings (`src/job_search_mcp/embeddings/`) default to a local
`SentenceTransformersEmbedder` (`all-MiniLM-L6-v2`) — see
`docs/adr/0006-embeddings-choice-open.md`.

## Stack

- Python, dependency management via [`uv`](https://docs.astral.sh/uv/)
- [`just`](https://github.com/casey/just) as the task runner (see `justfile`)
- Qdrant (default vector store), Notion (default tracking store, not yet wired up)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) for the server itself

## MCP tools

- **`match_job(job_description, source_url=None)`** — embeds the job
  description, retrieves the most relevant resume/experience chunks from
  the configured `VectorStore`, and returns a heuristic `fit_score`
  (top-match cosine similarity) plus the retrieved evidence. It does not
  synthesize strengths/gaps/notes itself — no internal LLM call — so the
  calling assistant is expected to reason over the returned evidence.

## Setup

1. `just install`
2. Copy `.env.example` to `.env` and fill in your Qdrant connection details.
3. Ingest a resume: `uv run python -m job_search_mcp.ingest path/to/resume.pdf`
4. Register with Claude Code (project-scoped):
   ```sh
   claude mcp add job-search-mcp -- uv run --directory "$(pwd)" job-search-mcp
   ```
5. In a Claude Code session in this project, ask it to call `match_job`
   with a real job description to validate retrieval quality.

## Roadmap

Current phase: `match_job` works standalone against real Qdrant, validated
against real job postings. Not yet wired to a tracking store.

Planned next:

- Notion `TrackingStore` integration — write `match_job` results somewhere durable
- Make the Notion tracking field mapping configurable via YAML instead of
  the current v1 hardcoded field list
  (`docs/adr/0004-tracking-field-mapping-v1-shortcut.md`)
- Local SQLite `TrackingStore` and self-hosted Qdrant-in-Docker
  `VectorStore` implementations for users without Notion/Qdrant Cloud
- Google Drive-backed `ResumeSource` implementation
- Revisit the embeddings choice if local sentence-transformers quality
  proves insufficient (`docs/adr/0006-embeddings-choice-open.md`)

## Development

```sh
just install   # uv sync
just test      # uv run pytest (unit tests only; integration needs QDRANT_URL)
just lint      # uv run ruff check .
just run       # uv run job-search-mcp (stdio MCP server)
```
