# 0001: Adapter pattern for storage and input

## Status

Accepted

## Context

`job-search-mcp` needs three external capabilities: a place to store and
search embedded resume/experience content (vector store), a place to
persist fit-analysis results (tracking store), and a way to retrieve resume
content in the first place (resume source). The author's own setup uses
Qdrant, Notion, and manually-exported PDF/DOCX files respectively, but
those are one person's tooling choices, not requirements of the matching
logic itself.

If the vector search, tracking writes, and resume parsing calls were made
directly against Qdrant's client, Notion's API, and a hardcoded file path
from within the matching/analysis code, every one of those choices would be
baked into the core logic. Anyone wanting to use a different vector
database, a different tracking system, or a different resume source would
need to fork or rewrite the matching logic itself, not just swap a
dependency.

## Decision

Define three Protocol interfaces — `VectorStore`, `TrackingStore`, and
`ResumeSource` — in `src/job_search_mcp/vector_store/base.py`,
`tracking_store/base.py`, and `resume_source/base.py` respectively. All
matching and analysis logic depends only on these interfaces, never on a
concrete implementation. Concrete implementations (e.g. `QdrantVectorStore`,
`NotionTrackingStore`, `FileResumeSource`) live alongside their interface
and satisfy it, but are otherwise interchangeable.

Each package (`vector_store/`, `tracking_store/`, `resume_source/`) pairs
its interface with the author's chosen default implementation. This keeps
the adapter boundary obvious from the directory layout itself: anyone
adding a new implementation adds a new file next to the existing ones, and
anyone wanting to see what's swappable can look at the interface in
`base.py`.

## Consequences

- New implementations (local SQLite tracking store, self-hosted
  Qdrant-in-Docker vector store, a Google Drive resume source, etc.) can be
  added without touching matching logic — they only need to satisfy the
  relevant Protocol.
- Matching/analysis code is easier to test, since any implementation can be
  swapped for a fake or in-memory one that satisfies the same interface.
- There is a small amount of added indirection compared to calling a vendor
  SDK directly — an extra layer to read through when tracing a call from
  matching logic down to Qdrant or Notion specifically.
- The interfaces themselves become a compatibility contract: changing a
  Protocol's method signature is a breaking change for every implementation,
  so they should be designed conservatively.
