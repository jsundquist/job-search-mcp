# 0008: Resume chunking strategy — light section-based chunking

## Status

Accepted. Supersedes the Phase 1 "whole-document, no chunker" decision.

## Context

During Phase 1 (standalone retrieval, before the MCP server existed), the
resume was embedded whole as a single vector record rather than chunked.
That call was made inline during that phase (not its own ADR at the time)
on the reasoning that the resume was short enough that chunking would be
over-engineering for a first pass at proving the retrieval mechanics
worked.

Once `match_job` existed and was validated against a real job posting
(a Staff Software Engineer, AI for Engineering Productivity role), that
assumption broke down. The single whole-document embedding returned a
`retrieval_score` (then named `fit_score`) of ~0.48 for that posting, and
reasoning manually over the same resume text suggested a much stronger
match — the posting is specifically about AI-assisted developer tooling,
and the resume has a directly relevant role (Backstage internal developer
platform, GenAI Hub plugin, MCP tooling integration) that whole-document
cosine similarity diluted into 16 years of otherwise-unrelated
financial-domain experience. Whole-document embedding worked fine for
Phase 1's purpose (prove retrieval mechanics work at all) but was the
wrong choice once retrieval *selectivity* mattered — surfacing the
specific relevant experience for a specific posting, rather than always
returning the entire resume as one undifferentiated chunk.

## Decision

Resume text is split into light, section/role-sized chunks
(`src/job_search_mcp/chunking.py`) before embedding, rather than embedded
as a single whole-document record. The chunker is a small structural
heuristic, not NLP-based section detection:

- a short, digit-free, comma-free line (e.g. "Experience", "Technical
  Skills") is treated as a section header and always starts a new chunk
- a longer non-bullet line (a role/title/company/date line) starts a new
  chunk only if the current chunk has already accumulated bulleted
  content — this is what separates one role/project from the next
- bulleted lines never start a new chunk; they accumulate under whatever
  role/section heading precedes them

This is deliberately not a general document chunker or an LLM-based
segmenter — it fits the shape of a typical resume (short headers, longer
title/date lines, bulleted achievements) and nothing more. `top_k`
retrieval (already part of the `VectorStore`/`retrieve` interfaces from
Phase 1) now does real work: a JD about a specific area can surface the
specific relevant role/chunk instead of always getting the entire resume
back diluted by irrelevant sections.

Getting real chunk-level ingestion working also surfaced two
format-specific extraction bugs, fixed alongside this change since
chunking is what exposed them (see `resume_source/file_source.py`):

- **PDF**: pypdf's default `extract_text()` fragmented at least one real
  resume PDF into near one-word-per-line output, which broke line-based
  chunking entirely (hundreds of single-word chunks). Fixed by using
  pypdf's `extraction_mode="layout"`, which preserves visual line wrapping
  far more faithfully. Chunk boundaries for PDF input are still coarser
  than for plain text/markdown/DOCX (a role's bullets can end up split
  across a few chunks instead of one) because PDF text still wraps
  mid-sentence in ways plain text doesn't — accepted as a known
  limitation rather than building a paragraph-reflow step for this phase.
- **DOCX**: native Word bulleted-list items store their bullet as
  paragraph-level list-numbering metadata (`<w:numPr>`), not as a literal
  character in `paragraph.text` — python-docx's plain text extraction
  drops it entirely, which meant the chunker's literal-bullet-character
  detection never fired and the entire Experience section collapsed into
  one chunk. Fixed by detecting `<w:numPr>` on each paragraph and
  prepending a literal "•" during extraction, so bullet structure survives
  into plain text the same way it does for the other formats.

## Consequences

- Retrieval can now surface a specific relevant role/section instead of
  always returning the whole resume, which is the actual goal of chunking
  (selectivity), not chunk-size management.
- `retrieval_score` (see `match_job.py`) is computed per-chunk and reported
  per-chunk in `retrieved_chunks`, so a caller can see *which* part of the
  resume drove the similarity, not just an undifferentiated whole-document
  number.
- Chunk quality is uneven across resume input formats: plain text/markdown
  and DOCX chunk cleanly into role/section-sized pieces; PDF chunks are
  coarser (more numerous, occasionally split mid-role) due to
  pypdf line-wrapping behavior even in layout mode. This is an accepted,
  documented tradeoff, not a silent gap — see `file_source.py`.
- The chunking heuristic is resume-shape-specific (short headers, bulleted
  achievements) and would need revisiting for a resume that doesn't follow
  that shape, or if `ResumeSource` implementations are added whose output
  doesn't preserve line structure well.
- Re-ingestion is required after this change — records upserted before
  this decision used a single `doc_id` as the record id; chunked ingestion
  now upserts one record per chunk under `{doc_id}::chunk-{i}`, so any
  previously-ingested whole-document record should be deleted and
  re-ingested rather than left alongside the new chunk records.
