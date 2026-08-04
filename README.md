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
  config — see Roadmap. Both read a user-declared `tracking_schema.yaml`
  (`docs/adr/0011-configurable-tracking-field-schema.md`) for which
  fields to write and read, rather than a mapping hardcoded to one
  specific Notion database.
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
  `job-fit://rubric` resource returned alongside it. Since
  `job_description` is often scraped/pasted web text, the result also
  includes it wrapped in an explicit data delimiter with a
  do-not-follow-instructions notice
  (`docs/adr/0017-delimit-job-description-in-match-job-result.md`).

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
  never creates a new row or searches for one. Only the fields your
  `tracking_schema.yaml` marks tool-populated are touched; every manual
  field on the row (company, comp range, source, work arrangement, etc.)
  is left as-is (`docs/adr/0011-configurable-tracking-field-schema.md`).
  A misconfigured field (e.g. a `notion.property` that no longer exists
  on your database) is skipped with a warning rather than failing the
  whole write — check the result's `warnings`. `dry_run=True` returns
  the mapped properties payload without writing.

- **`find_or_create_application(company, role, source_url=None, dry_run=False)`**
  — finds an existing tracked row by exact company+role text match, or
  creates a new one if none exists. Requires `company` and `role` fields
  with a `notion.property` declared in `tracking_schema.yaml`. Returns
  `{"job_id": ..., "created": bool}`. See
  `docs/adr/0013-find-or-create-application.md`.

- **`update_status(job_id, status, dry_run=False)`** — sets the Status
  field on an existing tracked row directly, for candidate-reported
  lifecycle events (Applied, Rejected, Interviewing, Offer, ...). Decoupled
  from `FitVerdict`/`push_to_tracker` entirely — see
  `docs/adr/0014-update-status-tool.md`.

`push_to_tracker` and `update_status` both verify the target `job_id`
actually belongs to your configured Notion database before writing to it
— see `docs/adr/0016-job-id-ownership-check.md`.

- **`list_applications(status=None)`** — lists tracked jobs from the
  configured `TrackingStore`, each with `job_id` plus whatever
  tool-populated fields your schema declares (typically `status`,
  `fit_rating`, `notes`). Pass `status` to filter to an exact
  (case-sensitive) match, e.g. `"Not yet applied"` — useful for questions
  like "what am I waiting to hear back on" without opening Notion.

Resume text is split into light, section/role-sized chunks before
embedding (`src/job_search_mcp/chunking.py`) rather than embedded whole —
see `docs/adr/0008-resume-chunking-strategy.md`.

## Tracking field schema

`push_to_tracker` and `list_applications` don't hardcode a field list —
they read `tracking_schema.yaml` (path overridable via
`TRACKING_SCHEMA_PATH`, gitignored like `.env`; copy
`tracking_schema.example.yaml` to get started). Each field is declared as
either:

- **`manual: true`** — the tool never reads or writes it (company, comp
  range, source, work arrangement, ...). Documentation only.
- **`derived_from: <status_fixed | fit_rating_from_bucket | key_notes>`**
  — a tool-populated field, computed from a `FitVerdict`. These three are
  the only values a `FitVerdict` can currently be turned into; the schema
  says which of them your tracker wants and under what property/column
  name, not how to compute them.

A tool-populated field also needs a backend location:
`notion.property`/`notion.type` for Notion, `sqlite.column` for
`SQLiteTrackingStore` (which only tracks fields that declare a
`sqlite.column` at all — it has no concept of Notion's manual fields).

Someone with a simpler tracker than the author's just lists fewer
fields. A misconfigured individual field (an unrecognized
`derived_from`, or a `notion.property` that doesn't exist on the live
database) is warned about and skipped rather than failing the whole
write; only an unreadable or structurally invalid schema file itself is
a hard failure. See `docs/adr/0011-configurable-tracking-field-schema.md`
for the full design.

## Setup

1. `just install`
2. Copy `.env.example` to `.env` and fill in your Qdrant and Notion
   connection details.
3. Copy `tracking_schema.example.yaml` to `tracking_schema.yaml` and edit
   the field list to match your own tracker (see Tracking field schema,
   above).
4. Ingest a resume: `uv run python -m job_search_mcp.ingest path/to/resume.pdf`
5. Register with Claude Code (project-scoped):
   ```sh
   claude mcp add job-search-mcp -- uv run --directory "$(pwd)" job-search-mcp
   ```
6. In a Claude Code session in this project, ask it to call `match_job`
   with a real job description, then `push_to_tracker` against a row you
   already track in Notion.

## Roadmap

Shipped: `match_job` (retrieval), `push_to_tracker`, `list_applications`,
`find_or_create_application`, and `update_status` against
`NotionTrackingStore`, the YAML-configurable tracking field schema
(`docs/adr/0011-configurable-tracking-field-schema.md`), and the ingestion
pipeline (`ResumeSource` → chunking → embedding → `VectorStore`).

Planned next:

- `evaluate_fit` — move fit-bucket judgment (the rubric in
  `docs/job_fit_scoring_algorithm.md`) inside the server via an internal
  LLM call, so it no longer depends on the calling assistant applying the
  rubric itself (`docs/adr/0009-caller-agnostic-reversal.md`,
  `docs/adr/0010-layer-split-design-evaluate-fit.md`)
- Wire `SQLiteTrackingStore` up as a selectable backend (it exists, reads
  the same tracking schema, and is tested, but the server currently
  always constructs `NotionTrackingStore`)
- Google Drive-backed `ResumeSource` implementation
- Revisit the embeddings choice if local sentence-transformers quality
  proves insufficient (`docs/adr/0006-embeddings-choice-open.md`)

Deferred, low priority (no design commitment beyond the note below):

- **Bulk re-evaluation when `candidate_profile.yaml` changes** —
  `target_floor`/`title_mapping_note` are documented as editable-but-stable,
  so a value changing after postings are already tracked is a foreseeable
  case. Open question: whether `list_applications` + re-running
  `evaluate_fit` is sufficient once that tool exists, or whether the
  original `job_description` text needs to be persisted somewhere (it
  currently isn't) to make re-evaluation possible later.
- **Duplicate/near-duplicate JD detection** — companies commonly post
  near-identical reqs for genuinely different underlying roles (same
  title, similar boilerplate, different team/contract). Neither
  `match_job`/`evaluate_fit` nor `find_or_create_application`
  (`docs/adr/0013-find-or-create-application.md`, which only matches
  exact company+role text) currently detect this. Direction: a
  lightweight hash/fuzzy-match check against previously-ingested
  postings, surfaced as a warning rather than blocking.

Both items above were raised alongside specific anecdotes (a mid-search
`target_floor` change; two near-duplicate "Skylight" postings) that a
`transcript-search` check found no independent record of — see
`docs/adr/0015-prompt-injection-defense-for-job-description-text.md`'s
Verification section for the same check applied to a related claim from
the same source. Both items stand on the general reasoning above
regardless of that.

## Development

```sh
just install   # uv sync
just test      # uv run pytest (unit tests only; integration needs QDRANT_URL)
just lint      # uv run ruff check .
just run       # uv run job-search-mcp (stdio MCP server)
```

CI (`.github/workflows/ci.yml`) runs lint and the unit test suite on
every push to `main` and every pull request.
