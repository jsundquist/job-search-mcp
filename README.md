# job-search-mcp

An MCP server that retrieves resume/experience evidence relevant to a job
description via RAG, and tracks fit-analysis results in a tracking store.

Analysis and tracking only — this project does not generate or tailor
resumes. See `docs/adr/0007-analysis-only-v1-no-resume-generation.md`.

## Design

The server is adapter-based rather than locked to any specific vendor.
Three interfaces define the boundaries:

- **`VectorStore`** (`src/job_search_mcp/vector_store/`) — embedded
  resume/experience chunk storage and similarity search. Default
  implementation: `QdrantVectorStore` (Cloud or self-hosted-in-Docker —
  a connection detail, not an interface difference).
- **`TrackingStore`** (`src/job_search_mcp/tracking_store/`) — persistence
  for fit-analysis results. `NotionTrackingStore` is the store the server
  wires up today (see Setup). `SQLiteTrackingStore` is a zero-dependency
  local implementation that also exists but isn't yet selectable via
  config — see Roadmap.
- **`ResumeSource`** (`src/job_search_mcp/resume_source/`) — retrieval of
  resume/experience content. Implementation: `FileResumeSource` (local
  text/markdown, PDF, and DOCX parsing).

Rationale for each of these decisions is recorded in `docs/adr/`.

Embeddings (`src/job_search_mcp/embeddings/`) default to a local
`SentenceTransformersEmbedder` (`all-MiniLM-L6-v2`) — see
`docs/adr/0006-embeddings-choice-open.md`.

## Stack

- Python, dependency management via [`uv`](https://docs.astral.sh/uv/)
- [`just`](https://github.com/casey/just) as the task runner (see `justfile`)
- Qdrant (vector store), Notion (tracking store)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) for the server itself

## MCP tools

- **`match_job(job_description, source_url=None)`** — embeds the job
  description, retrieves the most relevant resume/experience chunks from
  the configured `VectorStore`, and returns a heuristic `retrieval_score`
  (top-match cosine similarity) plus the retrieved evidence. Named
  `retrieval_score`, not `fit_score` — it's a retrieval confidence signal,
  not a fit judgment, and the two can diverge (see
  `docs/adr/0008-resume-chunking-strategy.md`). It does not synthesize a
  fit verdict itself — no internal LLM call — so the calling assistant is
  expected to reason over the returned evidence, applying the
  `job-fit://rubric` resource returned alongside it.

  Note: `docs/adr/0009-caller-agnostic-reversal.md` calls for this
  judgment step to move server-side into a new `evaluate_fit` tool, so
  fit-bucket assignment isn't left to whichever assistant happens to call
  `match_job`. That tool is designed (`docs/evaluate_fit_schema.md`,
  `docs/adr/0010-layer-split-design-evaluate-fit.md`) but **not yet
  implemented** — today, the calling assistant still constructs the
  `FitVerdict` passed to `push_to_tracker` itself.

- **`push_to_tracker(job_id, verdict, dry_run=False)`** — writes a
  `FitVerdict` (see `docs/evaluate_fit_schema.md`) to the configured
  `TrackingStore`. Updates an existing tracked row by Notion page ID —
  never creates a new row or searches for one. Only three properties are
  touched (Status, Fit Rating, Key Notes); every other property on the
  row is left as-is (`docs/adr/0004-tracking-field-mapping-v1-shortcut.md`).
  `dry_run=True` returns the mapped properties payload without writing.

- **`list_applications(status=None)`** — lists tracked jobs from the
  configured `TrackingStore`, each with `job_id`, `status`, `fit_rating`,
  and `notes`. Pass `status` to filter to an exact (case-sensitive) match,
  e.g. `"Not yet applied"` — useful for questions like "what am I waiting
  to hear back on" without opening Notion.

Resume text is split into light, section/role-sized chunks before
embedding (`src/job_search_mcp/chunking.py`) rather than embedded whole —
see `docs/adr/0008-resume-chunking-strategy.md`.

## Setup

1. `just install`
2. Copy `.env.example` to `.env` and fill in your Qdrant and Notion
   connection details.
3. Ingest a resume: `uv run python -m job_search_mcp.ingest path/to/resume.pdf`
4. Register with Claude Code (project-scoped):
   ```sh
   claude mcp add job-search-mcp -- uv run --directory "$(pwd)" job-search-mcp
   ```
5. In a Claude Code session in this project, ask it to call `match_job`
   with a real job description, then `push_to_tracker` against a row you
   already track in Notion.

## Roadmap

Shipped: `match_job` (retrieval), `push_to_tracker` and `list_applications`
against `NotionTrackingStore`, and the ingestion pipeline
(`ResumeSource` → chunking → embedding → `VectorStore`).

Planned next:

- `evaluate_fit` — move fit-bucket judgment (the rubric in
  `docs/job_fit_scoring_algorithm.md`) inside the server via an internal
  LLM call, so it no longer depends on the calling assistant applying the
  rubric itself (`docs/adr/0009-caller-agnostic-reversal.md`,
  `docs/adr/0010-layer-split-design-evaluate-fit.md`)
- Wire `SQLiteTrackingStore` up as a selectable backend (it exists and is
  tested, but the server currently always constructs `NotionTrackingStore`)
- Make the Notion tracking field mapping configurable via YAML instead of
  the current v1 hardcoded field list
  (`docs/adr/0004-tracking-field-mapping-v1-shortcut.md`)
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
